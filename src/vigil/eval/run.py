# SPDX-License-Identifier: Apache-2.0
"""Reproducible evaluation on synthetic data: ``python -m vigil.eval.run``.

Everything here is **synthetic**. Numbers show relative behaviour (fused vs
single-signal baselines, seen vs unseen wording, per-language gaps), not
real-world fraud performance. See ``docs/EVALUATION.md`` for caveats.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from vigil import MODEL_VERSION
from vigil.domain.models import AssessRequest, RiskAssessment, Tier
from vigil.eval.metrics import average_precision, confusion, precision_at_prevalence
from vigil.network.exchange import SignalExchange
from vigil.network.graph import MuleNetworkAnalyzer
from vigil.risk.calibration import expected_calibration_error
from vigil.risk.engine import RiskEngine
from vigil.synthetic.generator import Scenario, generate
from vigil.synthetic.network import generate_network

TEST_SEED = 2024
TEST_N = 6000
FRICTION = Tier.FRICTION.rank
NUDGE = Tier.NUDGE.rank


def _assess(engine: RiskEngine, s: Scenario, *, transcript: bool, txn: bool) -> RiskAssessment:
    return engine.assess(
        AssessRequest(
            profile=s.profile,
            transcript=s.transcript if transcript else [],
            txn=s.txn if txn else None,
        )
    )


def _amount_rule(s: Scenario) -> bool:
    """A typical static rule: large payment to a first-time payee."""
    return s.txn.amount_inr >= 50_000 and s.txn.payee_first_time


def _summarise(
    name: str, scores: list[float], tiers: list[int], labels: list[int]
) -> dict[str, Any]:
    c = confusion([t >= FRICTION for t in tiers], labels)
    soft = confusion([t >= NUDGE for t in tiers], labels)
    return {
        "system": name,
        "pr_auc": round(average_precision(scores, labels), 4),
        "friction": {
            k: (round(v, 4) if isinstance(v, float) else v)
            for k, v in c.items()
            if k != "recall_ci" and k != "fpr_ci"
        }
        | {
            "recall_ci": [round(x, 4) for x in c["recall_ci"]],
            "fpr_ci": [round(x, 4) for x in c["fpr_ci"]],
        },
        "nudge_or_higher": {"recall": round(soft["recall"], 4), "fpr": round(soft["fpr"], 4)},
        "precision_at_1pct": round(precision_at_prevalence(c["recall"], c["fpr"], 0.01), 4),
        "precision_at_0.1pct": round(precision_at_prevalence(c["recall"], c["fpr"], 0.001), 4),
    }


def evaluate_conversations(n: int = TEST_N, seed: int = TEST_SEED) -> dict[str, Any]:
    """Runs the fused model and baselines on held-out synthetic scenarios."""
    sc = generate(n, seed, scam_payee_pool=max(5, n // 12))
    engine = RiskEngine()
    labels = [s.label for s in sc]

    fused: list[RiskAssessment] = []
    lat: list[float] = []
    for s in sc:
        r = _assess(engine, s, transcript=True, txn=True)
        fused.append(r)
        lat.append(r.latency_ms)
    txn_only = [_assess(engine, s, transcript=False, txn=True) for s in sc]
    conv_only = [_assess(engine, s, transcript=True, txn=False) for s in sc]

    systems = [
        _summarise(
            "Static rule: ≥₹50k to first-time payee",
            [float(_amount_rule(s)) for s in sc],
            [FRICTION if _amount_rule(s) else 0 for s in sc],
            labels,
        ),
        _summarise(
            "Transaction signals only (what a bank sees today)",
            [r.score for r in txn_only],
            [r.tier.rank for r in txn_only],
            labels,
        ),
        _summarise(
            "Conversation only (no payment context)",
            [r.score for r in conv_only],
            [r.tier.rank for r in conv_only],
            labels,
        ),
        _summarise("Vigil fused", [r.score for r in fused], [r.tier.rank for r in fused], labels),
    ]

    def slice_recall(key: str) -> dict[str, Any]:
        groups: dict[str, list[int]] = defaultdict(list)
        for s, r in zip(sc, fused, strict=True):
            if s.label == 1:
                groups[
                    getattr(s, key) if key != "has_transcript" else s.meta["has_transcript"]
                ].append(int(r.tier.rank >= FRICTION))
        return {
            k: {"n": len(v), "recall": round(sum(v) / len(v), 4)} for k, v in sorted(groups.items())
        }

    benign_by_kind: dict[str, dict[str, float]] = {}
    kinds: dict[str, list[RiskAssessment]] = defaultdict(list)
    for s, r in zip(sc, fused, strict=True):
        if s.label == 0:
            kinds[s.kind].append(r)
    for k, rs in sorted(kinds.items()):
        benign_by_kind[k] = {
            "n": len(rs),
            "nudge_rate": round(sum(r.tier.rank == NUDGE for r in rs) / len(rs), 4),
            "friction_or_hold_rate": round(sum(r.tier.rank >= FRICTION for r in rs) / len(rs), 4),
        }

    # Time-to-intervene: seconds between the first FRICTION-level warning and the payment.
    leads: list[float] = []
    prevented = total = 0
    for s in sc:
        if s.label == 1 and s.transcript:
            total += 1
            t_flag = next(
                (
                    s.transcript[i - 1].t
                    for i in range(1, len(s.transcript) + 1)
                    if engine.conversation_score(s.transcript[:i]) >= 0.5
                ),
                None,
            )
            if t_flag is not None and t_flag < s.payment_t:
                prevented += 1
                leads.append(s.payment_t - t_flag)

    probs = np.array([r.score for r in fused])
    ece = expected_calibration_error(probs, np.array(labels, dtype=float))

    return {
        "n": n,
        "seed": seed,
        "scam_share": round(sum(labels) / n, 3),
        "systems": systems,
        "fused_recall_by_language": slice_recall("language"),
        "fused_recall_by_scam_type": slice_recall("kind"),
        "fused_recall_by_wording_family": slice_recall("family"),
        "fused_recall_by_transcript_available": slice_recall("has_transcript"),
        "benign_friction_by_kind": benign_by_kind,
        "time_to_intervene": {
            "scams_with_transcript": total,
            "warned_before_payment": prevented,
            "share_warned_before_payment": round(prevented / total, 4) if total else 0.0,
            "median_lead_seconds": round(statistics.median(leads), 1) if leads else None,
            "p10_lead_seconds": round(float(np.percentile(leads, 10)), 1) if leads else None,
        },
        "calibration_ece": round(ece, 4),
        "latency_ms": {
            "p50": round(float(np.percentile(lat, 50)), 2),
            "p95": round(float(np.percentile(lat, 95)), 2),
        },
    }


def evaluate_exchange(n: int = 4000, seed: int = TEST_SEED + 1) -> dict[str, Any]:
    """Online simulation of cross-bank signal sharing on transcript-free scams."""
    sc = generate(n, seed, transcript_available=0.0, scam_payee_pool=max(5, n // 40))
    banks = ["bank_a", "bank_b", "bank_c"]

    def run(use_exchange: bool) -> tuple[int, int, int, int]:
        ex = SignalExchange(b"eval-key-eval-key-eval-key-eval!", min_reporters=2)
        engine = RiskEngine(payee_check=ex.payee_check() if use_exchange else None)
        tp = fn = fp = tn = 0
        half = n // 2
        for i, s in enumerate(sc):
            r = engine.assess(AssessRequest(profile=s.profile, transcript=[], txn=s.txn))
            blocked = r.tier.rank >= FRICTION
            if i >= half:
                if s.label:
                    tp, fn = tp + blocked, fn + (not blocked)
                else:
                    fp, tn = fp + blocked, tn + (not blocked)
            if use_exchange and s.label and (i % 10) < 7:  # most losses get confirmed and reported
                ex.publish(banks[i % 3], "payee", s.txn.payee_ref)
        return tp, fn, fp, tn

    out: dict[str, Any] = {
        "n": n,
        "note": "second half evaluated; scams have no transcript (payment signals only)",
    }
    for name, flag in (("without_exchange", False), ("with_exchange", True)):
        tp, fn, fp, tn = run(flag)
        out[name] = {
            "recall": round(tp / (tp + fn), 4) if tp + fn else 0.0,
            "fpr": round(fp / (fp + tn), 4) if fp + tn else 0.0,
        }
    return out


def evaluate_network(seed: int = 777) -> dict[str, Any]:
    """Mule-account detection vs simple rules on a synthetic month of transfers."""
    net = generate_network(seed=seed)
    res = MuleNetworkAnalyzer().analyze(net.transfers, net.accounts)
    mules, hard = net.mules, net.hard_negatives

    def prf(flagged: set[str]) -> dict[str, float]:
        tp = len(flagged & mules)
        return {
            "flagged": len(flagged),
            "precision": round(tp / len(flagged), 4) if flagged else 0.0,
            "recall": round(tp / len(mules), 4),
            "hard_negatives_flagged": len(flagged & hard),
        }

    vigil = {a for a, n in res.nodes.items() if n.score >= 0.5}
    fan_in = {a for a, n in res.nodes.items() if n.distinct_senders >= 8}
    passthrough = {a for a, n in res.nodes.items() if n.features["passthrough"] >= 0.8}
    ring_hit = sum(
        1
        for ring in set(net.ring_of.values())
        if len({m for m, r in net.ring_of.items() if r == ring} & vigil)
        / sum(1 for r in net.ring_of.values() if r == ring)
        >= 0.5
    )
    return {
        "accounts": len(net.accounts),
        "transfers": len(net.transfers),
        "true_mules": len(mules),
        "hard_negative_accounts": len(hard),
        "rules": {
            "fan-in ≥ 8 senders": prf(fan_in),
            "pass-through ≥ 80% only": prf(passthrough),
            "Vigil network score ≥ 0.5": prf(vigil),
        },
        "rings_total": len(set(net.ring_of.values())),
        "rings_with_majority_recovered": ring_hit,
        "rings_reported": len(res.rings),
    }


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="artifacts/eval", help="output directory")
    ap.add_argument("--ui", default=None, help="also write results.json for the web UI here")
    ap.add_argument("--quick", action="store_true", help="smaller run for CI")
    args = ap.parse_args(argv)

    t0 = time.time()
    n = 1500 if args.quick else TEST_N
    result: dict[str, Any] = {
        "model_version": MODEL_VERSION,
        "disclaimer": "Synthetic data only. Relative comparisons, not real-world performance.",
        "conversations": evaluate_conversations(n),
        "exchange": evaluate_exchange(1500 if args.quick else 4000),
        "network": evaluate_network(),
        "runtime_s": round(time.time() - t0, 1),
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    if args.ui:
        Path(args.ui).parent.mkdir(parents=True, exist_ok=True)
        Path(args.ui).write_text(json.dumps(result, ensure_ascii=False))
    print(json.dumps(result["conversations"]["systems"], indent=1, ensure_ascii=False))
    print(
        json.dumps(
            {"exchange": result["exchange"], "network": result["network"]},
            indent=1,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
