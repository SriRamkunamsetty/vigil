# SPDX-License-Identifier: Apache-2.0
"""ADK tools. They are thin wrappers over deterministic services.

Rules the tools enforce regardless of what any model says:

* ``assess_call_risk`` returns the engine's tier; the agent may explain it but
  has no tool to change or override it.
* Anything that affects another person or institution
  (``notify_trusted_contact``, ``publish_signal``) is a
  ``FunctionTool(require_confirmation=True)``, so a human must approve it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.function_tool import FunctionTool

from vigil.domain.models import (
    AssessRequest,
    Language,
    Speaker,
    TransactionContext,
    UserProfile,
    Utterance,
)
from vigil.services import Services

DEMO_REPORTER = "demo-bank-a"


def _parse_lines(lines: list[str]) -> list[Utterance]:
    out: list[Utterance] = []
    for i, raw in enumerate(lines[:100]):
        who, _, text = raw.partition(":")
        speaker = (
            Speaker.USER if who.strip().lower() in {"user", "me", "customer"} else Speaker.CALLER
        )
        body = text.strip() if text else raw.strip()
        out.append(Utterance(speaker=speaker, text=body[:2000], t=float(i * 6)))
    return out


@dataclass
class ToolSets:
    """Tools grouped per agent."""

    guardian: list[BaseTool]
    investigator: list[BaseTool]
    payment_guard: list[BaseTool]


def build_tools(svc: Services) -> ToolSets:
    """Creates the tool sets bound to ``svc``."""

    async def assess_call_risk(
        conversation: list[str],
        language: str = "en",
        senior: bool = False,
        amount_inr: float = 0.0,
        payee: str = "",
        payee_first_time: bool = False,
        on_active_call: bool = False,
    ) -> dict[str, Any]:
        """Scores a call/chat (and optional pending payment) for scam risk.

        Args:
            conversation: Lines like "caller: your account will be blocked" or
                "user: ok". Lines without a prefix are treated as the caller.
            language: Preferred reply language: en, hi or te.
            senior: True if the person opted in to extra protection.
            amount_inr: Pending payment amount in rupees, 0 if none.
            payee: Payee UPI ID or account, empty if none.
            payee_first_time: True if the person has never paid this payee.
            on_active_call: True if the person is on a call with an unknown number.

        Returns:
            The deterministic decision: tier (allow/nudge/friction/hold), score,
            scam_type, top reasons and the recommended steps. Relay it as is; do
            not soften or override the tier.
        """
        lang = Language(language) if language in {"en", "hi", "te"} else Language.EN
        txn = (
            TransactionContext(
                amount_inr=amount_inr,
                payee_ref=payee or "unknown",
                payee_first_time=payee_first_time,
                active_call_with_unknown_number=on_active_call,
            )
            if amount_inr > 0
            else None
        )
        req = AssessRequest(
            profile=UserProfile(user_id="agent-session", preferred_language=lang, senior=senior),
            transcript=_parse_lines(conversation),
            txn=txn,
        )
        a = await svc.assess(req)
        iv = a.intervention
        return {
            "tier": a.tier.value,
            "score": a.score,
            "scam_type": a.scam_type.value,
            "reasons": [d.label for d in a.drivers[:4]],
            "evidence": [e.excerpt for e in a.evidence[:3]],
            "headline": iv.headline if iv else "",
            "steps": iv.steps if iv else [],
            "hold_payment": a.actions.hold_for_review,
            "offer_trusted_contact_alert": a.actions.offer_trusted_contact_alert,
        }

    def check_payee_signal(payee: str) -> dict[str, Any]:
        """Checks whether other banks have reported this payee (hashed lookup).

        Args:
            payee: UPI ID or account number.

        Returns:
            flag (0 none, 0.6 one report, 1.0 corroborated) and reporter count.
        """
        r = svc.exchange.lookup("payee", payee)
        return {"flag": r.flag, "reporters": r.reporters, "corroborated": r.corroborated}

    def notify_trusted_contact(reason: str) -> dict[str, Any]:
        """Alerts the person's pre-chosen trusted contact. Needs the person's approval.

        Args:
            reason: One plain sentence on why, without account numbers.

        Returns:
            Delivery status (the demo does not send real messages).
        """
        return {
            "status": "queued_demo",
            "note": "Demo mode: no real message is sent.",
            "reason": reason[:200],
        }

    def list_rings() -> list[dict[str, Any]]:
        """Lists suspected mule rings found in the demo transfer graph.

        Returns:
            Ring id, size, victims and exposure for each ring.
        """
        _, res = svc.network()
        return [
            {
                "ring_id": r.ring_id,
                "accounts": len(r.members),
                "victims": r.victims,
                "exposure_inr": r.exposure_inr,
                "score": r.score,
            }
            for r in res.rings
        ]

    async def explain_ring(ring_id: str) -> dict[str, Any]:
        """Explains one ring for an investigator, with a plain-language case note.

        Args:
            ring_id: A ring id from list_rings, such as "R-01".

        Returns:
            Case note, entry and cash-out account counts and per-account reasons.
        """
        _, res = svc.network()
        ring = next((r for r in res.rings if r.ring_id == ring_id), None)
        if ring is None:
            return {"error": f"unknown ring {ring_id}"}
        note = await svc.composer.case_note(ring) if svc.composer else ring.narrative
        return {
            "note": note,
            "entry_accounts": len(ring.entry_accounts),
            "cashout_accounts": len(ring.cashout_accounts),
            "top_accounts": [
                {"account": m, "score": res.nodes[m].score, "reasons": res.nodes[m].reasons[:3]}
                for m in ring.members[:5]
            ],
        }

    def publish_signal(ring_id: str) -> dict[str, Any]:
        """Shares the ring's account identifiers (as keyed hashes) with partner banks. Needs a human's approval.

        Args:
            ring_id: A ring id from list_rings.

        Returns:
            How many hashed signals were published.
        """
        _, res = svc.network()
        ring = next((r for r in res.rings if r.ring_id == ring_id), None)
        if ring is None:
            return {"error": f"unknown ring {ring_id}"}
        for acct in ring.members:
            svc.exchange.publish(DEMO_REPORTER, "payee", acct)
        return {"published": len(ring.members), "reporter": DEMO_REPORTER}

    def list_agent_payment_cases() -> list[dict[str, str]]:
        """Lists the agent-payment scenarios available to verify.

        Returns:
            Case id, title and the expected outcome of each scenario.
        """
        return [
            {"case_id": c.case_id, "title": c.title, "expected": c.expected}
            for c in svc.payments.cases.values()
        ]

    def verify_agent_payment(case_id: str) -> dict[str, Any]:
        """Verifies a signed AI-agent purchase against the user's mandate.

        Args:
            case_id: A case id from list_agent_payment_cases.

        Returns:
            approve, step_up or deny with the checks that failed.
        """
        if case_id not in svc.payments.cases:
            return {"error": f"unknown case {case_id}"}
        case, v = svc.payments.run_case(case_id)
        return {
            "decision": v.decision,
            "risk_score": v.risk_score,
            "reasons": v.reasons,
            "failed_checks": [c.name for c in v.checks if not c.passed],
            "story": case.story,
        }

    return ToolSets(
        guardian=[
            FunctionTool(assess_call_risk),
            FunctionTool(check_payee_signal),
            FunctionTool(notify_trusted_contact, require_confirmation=True),
        ],
        investigator=[
            FunctionTool(list_rings),
            FunctionTool(explain_ring),
            FunctionTool(publish_signal, require_confirmation=True),
        ],
        payment_guard=[FunctionTool(list_agent_payment_cases), FunctionTool(verify_agent_payment)],
    )
