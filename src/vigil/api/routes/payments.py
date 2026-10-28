# SPDX-License-Identifier: Apache-2.0
"""AI-agent payment guard endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from vigil.api.deps import Caller, Svc
from vigil.obs import audit_logger
from vigil.payments.mandate import SignedMandate, Verdict

router = APIRouter(prefix="/v1/agent-payments", tags=["agent-payments"])


@router.get("/cases", summary="Demo scenarios")
async def cases(svc: Svc) -> list[dict[str, Any]]:
    """Scenario list with the signed intent and cart payloads for inspection."""
    out = []
    for c in svc.payments.cases.values():
        out.append(
            {
                "case_id": c.case_id,
                "title": c.title,
                "story": c.story,
                "expected": c.expected,
                "agent_id": c.agent_id,
                "intent": c.intent.payload,
                "cart": c.cart.payload,
            }
        )
    return out


class DemoVerifyIn(BaseModel):
    """Run a built-in scenario."""

    case_id: str = Field(pattern=r"^[a-z_]{3,32}$")


@router.post("/verify-demo", summary="Verify a built-in scenario")
async def verify_demo(body: DemoVerifyIn, svc: Svc, caller: Caller) -> dict[str, Any]:
    """Runs the guard on a fresh state so the result is reproducible."""
    if body.case_id not in svc.payments.cases:
        raise HTTPException(404, "Unknown case.")
    case, v = svc.payments.run_case(body.case_id)
    audit_logger.info(
        "agent_payment_verified",
        extra={"caller": caller, "case": case.case_id, "decision": v.decision},
    )
    return {
        "case_id": case.case_id,
        "title": case.title,
        "expected": case.expected,
        "verdict": v.model_dump(),
    }


class VerifyIn(BaseModel):
    """A real verification request."""

    intent: SignedMandate
    cart: SignedMandate
    agent_id: str = Field(max_length=128)


@router.post("/verify", response_model=Verdict, summary="Verify a signed intent + cart")
async def verify(body: VerifyIn, svc: Svc, caller: Caller) -> Verdict:
    """Checks signatures, scope, budget, merchant, replay, prompt-injection text and more.

    In the demo the key registry holds only the demo wallet and merchants; a
    production deployment loads institution-managed keys.
    """
    from vigil.payments.mandate import MandateGuard

    guard: MandateGuard = svc.payment_guard
    v = guard.verify(body.intent, body.cart, body.agent_id)
    audit_logger.info("agent_payment_verified", extra={"caller": caller, "decision": v.decision})
    return v
