# SPDX-License-Identifier: Apache-2.0
"""Explainable mule-account and mule-ring detection on a transfer graph.

Mule accounts receive money from many victims and forward it within minutes.
Per-account scores use the same additive log-odds design as the risk model, so
every flag can be justified to an investigator or a regulator. Rings are the
connected components of high-scoring accounts.
"""

from __future__ import annotations

import bisect
import statistics
from collections import defaultdict
from dataclasses import dataclass, field

import networkx as nx
from pydantic import BaseModel, Field

from vigil.risk.scam_signals import logistic

PASS_WINDOW_S = 2 * 3600
NODE_THRESHOLD = 0.5
BIAS = -5.2
WEIGHTS = {
    "passthrough": 3.4,
    "fan_in": 1.8,
    "fan_out": 0.8,
    "young_account": 1.6,
    "shared_device": 1.9,
    "merchant": -2.4,
    "single_source": -1.4,
    "suspicious_upstream": 3.0,
    "suspicious_downstream": 1.2,
}
LABELS = {
    "passthrough": "Forwards most incoming money within 2 hours",
    "fan_in": "Receives from many unrelated senders",
    "fan_out": "Splits money out to several accounts",
    "young_account": "Account opened very recently",
    "shared_device": "Device shared with other flagged-type accounts",
    "merchant": "Registered merchant (protective)",
    "single_source": "Funded by a single regular source, e.g. payroll (protective)",
    "suspicious_upstream": "Most of its money comes from other flagged accounts",
    "suspicious_downstream": "Passes money on to other flagged accounts",
}
PROPAGATION_ROUNDS = 3


@dataclass(frozen=True)
class Transfer:
    """A completed account-to-account transfer."""

    src: str
    dst: str
    amount: float
    ts: float  # seconds


@dataclass
class AccountMeta:
    """Minimal account attributes. IDs are pseudonymous tokens."""

    account_id: str
    age_days: int = 365
    device_ids: tuple[str, ...] = ()
    is_merchant: bool = False


class NodeFinding(BaseModel):
    """A flagged account with its additive explanation."""

    account_id: str
    score: float = Field(ge=0, le=1)
    features: dict[str, float]
    reasons: list[str]
    inflow: float
    outflow: float
    distinct_senders: int


class RingFinding(BaseModel):
    """A connected group of suspicious accounts."""

    ring_id: str
    members: list[str]
    entry_accounts: list[str]
    cashout_accounts: list[str]
    score: float
    exposure_inr: float
    victims: int
    layering_depth: int
    median_dwell_minutes: float
    window_hours: float
    narrative: str


@dataclass
class NetworkResult:
    """Analysis output."""

    nodes: dict[str, NodeFinding] = field(default_factory=dict)
    rings: list[RingFinding] = field(default_factory=list)
    graph: nx.DiGraph = field(default_factory=nx.DiGraph)


def _clip(x: float) -> float:
    return max(0.0, min(1.0, x))


def _passthrough(ins: list[Transfer], outs: list[Transfer]) -> tuple[float, list[float]]:
    """Fraction of inflow forwarded within the window, and the dwell times."""
    if not ins or not outs:
        return 0.0, []
    outs = sorted(outs, key=lambda t: t.ts)
    remaining = [o.amount for o in outs]
    times = [o.ts for o in outs]
    matched = 0.0
    dwell: list[float] = []
    for i in sorted(ins, key=lambda t: t.ts):
        need = i.amount
        j = bisect.bisect_right(times, i.ts)
        while need > 1e-9 and j < len(outs) and times[j] - i.ts <= PASS_WINDOW_S:
            take = min(need, remaining[j])
            if take > 0:
                remaining[j] -= take
                need -= take
                matched += take
                dwell.append(times[j] - i.ts)
            j += 1
    total_in = sum(t.amount for t in ins)
    return min(1.0, matched / total_in), dwell


class MuleNetworkAnalyzer:
    """Scores accounts and extracts rings from a set of transfers."""

    def analyze(self, transfers: list[Transfer], accounts: dict[str, AccountMeta]) -> NetworkResult:
        """Runs account scoring, ring extraction and narrative generation."""
        ins: dict[str, list[Transfer]] = defaultdict(list)
        outs: dict[str, list[Transfer]] = defaultdict(list)
        g = nx.DiGraph()
        for t in transfers:
            ins[t.dst].append(t)
            outs[t.src].append(t)
            if g.has_edge(t.src, t.dst):
                g[t.src][t.dst]["amount"] += t.amount
                g[t.src][t.dst]["count"] += 1
            else:
                g.add_edge(t.src, t.dst, amount=t.amount, count=1)

        device_accounts: dict[str, set[str]] = defaultdict(set)
        for a in accounts.values():
            for d in a.device_ids:
                device_accounts[d].add(a.account_id)

        result = NetworkResult(graph=g)
        dwell_by_acct: dict[str, list[float]] = {}
        base: dict[str, dict[str, float]] = {}
        for acct, meta in accounts.items():
            i, o = ins.get(acct, []), outs.get(acct, [])
            if not i:
                continue
            senders = {t.src for t in i}
            receivers = {t.dst for t in o}
            pt, dwell = _passthrough(i, o)
            dwell_by_acct[acct] = dwell
            age = meta.age_days
            shared = max((len(device_accounts[d]) - 1 for d in meta.device_ids), default=0)
            base[acct] = {
                "passthrough": pt,
                "fan_in": _clip((len(senders) - 2) / 10),
                "fan_out": _clip((len(receivers) - 1) / 4),
                "young_account": 1.0 if age < 30 else 0.5 if age < 90 else 0.0,
                "shared_device": _clip(shared / 3),
                "merchant": 1.0 if meta.is_merchant else 0.0,
                "single_source": 1.0 if len(senders) == 1 and age >= 180 else 0.0,
            }

        # Guilt-by-association: re-score using how much of an account's money
        # comes from / goes to accounts flagged in the previous round.
        prev: set[str] = set()
        for _ in range(PROPAGATION_ROUNDS):
            current: dict[str, NodeFinding] = {}
            for acct, feats0 in base.items():
                i, o = ins[acct], outs.get(acct, [])
                total_in = sum(t.amount for t in i)
                total_out = sum(t.amount for t in o)
                up = sum(t.amount for t in i if t.src in prev) / total_in if total_in else 0.0
                down = sum(t.amount for t in o if t.dst in prev) / total_out if total_out else 0.0
                feats = dict(feats0)
                feats["suspicious_upstream"] = up
                feats["suspicious_downstream"] = down
                if up > 0.5:
                    feats["single_source"] = 0.0
                logit = BIAS + sum(WEIGHTS[k] * v for k, v in feats.items())
                contribs = sorted(
                    ((WEIGHTS[k] * v, k) for k, v in feats.items() if v > 0),
                    key=lambda kv: -abs(kv[0]),
                )
                current[acct] = NodeFinding(
                    account_id=acct,
                    score=round(logistic(logit), 4),
                    features={k: round(v, 3) for k, v in feats.items()},
                    reasons=[LABELS[k] for c, k in contribs if abs(c) > 0.3],
                    inflow=round(total_in, 2),
                    outflow=round(total_out, 2),
                    distinct_senders=len({t.src for t in i}),
                )
            result.nodes = current
            now = {a for a, n in current.items() if n.score >= NODE_THRESHOLD}
            if now == prev:
                break
            prev = now

        flagged = {a for a, n in result.nodes.items() if n.score >= NODE_THRESHOLD}
        result.rings = self._rings(g, flagged, result, dwell_by_acct, ins)
        return result

    def _rings(
        self,
        g: nx.DiGraph,
        flagged: set[str],
        result: NetworkResult,
        dwell_by_acct: dict[str, list[float]],
        ins: dict[str, list[Transfer]],
    ) -> list[RingFinding]:
        sub = g.subgraph(flagged)
        rings: list[RingFinding] = []
        comps = sorted(nx.weakly_connected_components(sub), key=lambda c: -len(c))
        for idx, comp in enumerate(comps, start=1):
            members = sorted(comp)
            # Entry accounts take money from outside the ring; cash-out accounts
            # send money to destinations outside the ring (or nowhere).
            entry = [m for m in members if any(t.src not in comp for t in ins.get(m, []))]
            cashout = [m for m in members if not any(s in comp for s in g.successors(m))]
            external_in = [t for m in members for t in ins.get(m, []) if t.src not in comp]
            victims = len({t.src for t in external_in})
            exposure = sum(t.amount for t in external_in)
            ts = [t.ts for t in external_in] or [0.0]
            dwell = [d for m in members for d in dwell_by_acct.get(m, [])]
            med_dwell = statistics.median(dwell) / 60 if dwell else 0.0
            depth = self._depth(sub)
            score = 1 - 1.0
            for m in members:
                score = 1 - (1 - score) * (1 - result.nodes[m].score)
            if len(members) < 2 and victims < 3:
                continue
            ring = RingFinding(
                ring_id=f"R-{idx:02d}",
                members=members,
                entry_accounts=entry,
                cashout_accounts=cashout,
                score=round(min(score, 0.999), 3),
                exposure_inr=round(exposure, 2),
                victims=victims,
                layering_depth=depth,
                median_dwell_minutes=round(med_dwell, 1),
                window_hours=round((max(ts) - min(ts)) / 3600, 1),
                narrative="",
            )
            ring.narrative = narrative_for(ring)
            rings.append(ring)
        rings.sort(key=lambda r: -r.exposure_inr)
        for i, r in enumerate(rings, start=1):
            r.ring_id = f"R-{i:02d}"
            r.narrative = narrative_for(r)
        return rings

    @staticmethod
    def _depth(sub: nx.DiGraph) -> int:
        """Longest hop chain inside the ring (cycles are condensed)."""
        if sub.number_of_nodes() == 0:
            return 0
        dag = nx.condensation(sub)
        return int(nx.dag_longest_path_length(dag)) + 1


def narrative_for(r: RingFinding) -> str:
    """Deterministic, plain-language case note for a ring."""
    return (
        f"Ring {r.ring_id}: {len(r.members)} linked accounts received "
        f"₹{r.exposure_inr:,.0f} from {r.victims} distinct senders over about "
        f"{r.window_hours:g} hours and forwarded it through {r.layering_depth} "
        f"layer(s), with a median hold time of {r.median_dwell_minutes:g} minutes. "
        f"{len(r.entry_accounts)} account(s) collect victim payments and "
        f"{len(r.cashout_accounts)} account(s) appear to cash out. Recommend: "
        "freeze outgoing transfers for review, request KYC re-verification, and "
        "share hashed identifiers with partner institutions after human approval."
    )
