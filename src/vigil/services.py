# SPDX-License-Identifier: Apache-2.0
"""Dependency container shared by the REST API and the ADK agents."""

from __future__ import annotations

import asyncio
import base64
import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from vigil.agents.composer import InterventionComposer
from vigil.agents.llm import GeminiJsonClient, JsonLLM
from vigil.agents.semantic import SemanticAnalyzer
from vigil.config import Settings, get_settings
from vigil.domain.models import (
    AssessRequest,
    Language,
    RiskAssessment,
    Tier,
    Utterance,
)
from vigil.network.exchange import SignalExchange
from vigil.network.graph import MuleNetworkAnalyzer, NetworkResult
from vigil.payments.demo import AgentPaymentDemo
from vigil.payments.mandate import MandateGuard
from vigil.risk.engine import RiskEngine
from vigil.synthetic.network import SyntheticNetwork, generate_network

log = logging.getLogger(__name__)


@dataclass
class Session:
    """A live conversation being monitored."""

    session_id: str
    profile_language: Language
    senior: bool
    utterances: list[Utterance] = field(default_factory=list)
    touched: float = field(default_factory=time.monotonic)


class SessionStore:
    """Bounded in-memory session store with TTL (swap for Firestore/Redis in prod)."""

    def __init__(self, ttl_s: int, max_sessions: int) -> None:
        """Creates a store."""
        self._ttl = ttl_s
        self._max = max_sessions
        self._items: OrderedDict[str, Session] = OrderedDict()
        self._lock = threading.Lock()

    def get_or_create(self, sid: str, language: Language, senior: bool) -> Session:
        """Returns the session, creating it (and evicting old ones) if needed."""
        now = time.monotonic()
        with self._lock:
            for k in [k for k, s in self._items.items() if now - s.touched > self._ttl]:
                del self._items[k]
            s = self._items.get(sid)
            if s is None:
                while len(self._items) >= self._max:
                    self._items.popitem(last=False)
                s = Session(sid, language, senior)
                self._items[sid] = s
            s.touched = now
            self._items.move_to_end(sid)
            return s

    def delete(self, sid: str) -> bool:
        """Deletes a session (user-initiated erase)."""
        with self._lock:
            return self._items.pop(sid, None) is not None

    def __len__(self) -> int:
        """Number of live sessions."""
        return len(self._items)


class Services:
    """Wires the engine, exchange, analyzers and (optional) Gemini adapters."""

    def __init__(self, settings: Settings | None = None, llm: JsonLLM | None = None) -> None:
        """Builds all components.

        Args:
            settings: Configuration (defaults to environment).
            llm: Override the JSON LLM (tests inject a scripted fake).
        """
        self.settings = settings or get_settings()
        s = self.settings
        key = base64.b64decode(s.signal_key)
        self.exchange = SignalExchange(
            key, min_reporters=s.signal_min_reporters, ttl_days=s.signal_ttl_days
        )
        self.engine = RiskEngine(payee_check=self.exchange.payee_check())
        self.mule = MuleNetworkAnalyzer()
        self.payments = AgentPaymentDemo()
        self.payment_guard = MandateGuard(
            self.payments.registry, reference_prices={"footwear": 2500, "gift_card": 3000}
        )
        self.sessions = SessionStore(s.session_ttl_s, s.max_sessions)
        self.llm: JsonLLM | None = llm
        if self.llm is None and s.llm_enabled:
            self.llm = GeminiJsonClient(s.model_fast, timeout_s=s.llm_timeout_s)
        self.semantic = SemanticAnalyzer(self.llm) if self.llm else None
        self.composer = InterventionComposer(self.llm) if self.llm else None
        self._net: tuple[SyntheticNetwork, NetworkResult] | None = None
        self._net_lock = threading.Lock()

    # -- risk ---------------------------------------------------------------

    async def assess(self, req: AssessRequest, use_ai: bool = True) -> RiskAssessment:
        """Assesses a request.

        The deterministic result is always produced; Gemini can only add tactic
        evidence and re-word the intervention.
        """
        acts: dict[Any, float] = {}
        evid: list[Any] = []
        layer = "off"
        if use_ai and self.semantic is not None and req.transcript:
            try:
                acts, evid, ok = await asyncio.wait_for(
                    self.semantic.analyze(req.transcript), timeout=self.settings.llm_timeout_s + 1
                )
                layer = "used" if ok else "unavailable"
            except (TimeoutError, Exception):
                acts, evid, layer = {}, [], "unavailable"
        result = self.engine.assess(req, extra_activations=acts or None, extra_evidence=evid)
        result.ai_layer = layer
        if (
            use_ai
            and self.composer is not None
            and result.tier is not Tier.ALLOW
            and result.intervention
        ):
            try:
                better = await asyncio.wait_for(
                    self.composer.compose(result, req.profile.preferred_language),
                    timeout=self.settings.llm_timeout_s + 1,
                )
                if better is not None:
                    result.intervention = better
            except Exception:
                log.info("composer_unavailable")
        return result

    # -- network ------------------------------------------------------------

    def network(self) -> tuple[SyntheticNetwork, NetworkResult]:
        """Returns the cached demo network and its analysis."""
        with self._net_lock:
            if self._net is None:
                net = generate_network(n_accounts=600, n_rings=4, seed=11)
                self._net = (net, self.mule.analyze(net.transfers, net.accounts))
            return self._net

    def ring_view(self, ring_id: str) -> dict[str, Any] | None:
        """Graph payload for one ring: nodes, edges and victims (pseudonymous IDs)."""
        _, res = self.network()
        ring = next((r for r in res.rings if r.ring_id == ring_id), None)
        if ring is None:
            return None
        members = set(ring.members)
        victims: set[str] = set()
        edges: list[dict[str, Any]] = []
        for u, v, d in res.graph.edges(data=True):
            if v in members and u not in members:
                victims.add(u)
            if v in members or (u in members and v in members):
                edges.append(
                    {"src": u, "dst": v, "amount": round(d["amount"]), "count": d["count"]}
                )
        vlist = sorted(victims)[:14]
        nodes = [
            {
                "id": m,
                "kind": "entry"
                if m in ring.entry_accounts
                else "cashout"
                if m in ring.cashout_accounts
                else "layer",
                "score": res.nodes[m].score,
                "reasons": res.nodes[m].reasons,
            }
            for m in ring.members
        ] + [{"id": v, "kind": "victim", "score": 0.0, "reasons": []} for v in vlist]
        keep = members | set(vlist)
        edges = [e for e in edges if e["src"] in keep and e["dst"] in keep]
        return {
            "ring": ring.model_dump(),
            "nodes": nodes,
            "edges": edges,
            "victims_total": ring.victims,
        }


_singleton: Services | None = None
_lock = threading.Lock()


def get_services() -> Services:
    """Returns the process-wide :class:`Services`."""
    global _singleton
    with _lock:
        if _singleton is None:
            _singleton = Services()
        return _singleton


def reset_services() -> None:
    """Drops the singleton (tests)."""
    global _singleton
    with _lock:
        _singleton = None
