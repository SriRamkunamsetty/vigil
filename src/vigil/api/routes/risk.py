# SPDX-License-Identifier: Apache-2.0
"""Risk assessment endpoints."""

from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field

from vigil.api.deps import Caller, Svc
from vigil.demo_data import DEMO_CALLS
from vigil.domain.models import (
    AssessRequest,
    Language,
    RiskAssessment,
    Speaker,
    TransactionContext,
    UserProfile,
    Utterance,
)
from vigil.obs import audit_logger

router = APIRouter(prefix="/v1", tags=["risk"])
SessionId = Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{6,64}$")]


def _audit(event: str, caller: str, a: RiskAssessment, **extra: object) -> None:
    """Logs a decision without any content (no transcript, payee or amount)."""
    audit_logger.info(
        event,
        extra={
            "caller": caller,
            "tier": a.tier.value,
            "score": a.score,
            "scam_type": a.scam_type.value,
            "phase": a.phase,
            "ai_layer": a.ai_layer,
            "model_version": a.model_version,
            **extra,
        },
    )


@router.post(
    "/assess", response_model=RiskAssessment, summary="Assess a conversation and/or payment"
)
async def assess(req: AssessRequest, svc: Svc, caller: Caller, ai: bool = True) -> RiskAssessment:
    """Deterministic risk decision with explanations. ``ai=false`` skips Gemini entirely."""
    a = await svc.assess(req, use_ai=ai)
    _audit("assess", caller, a)
    return a


class TimelinePoint(BaseModel):
    """Risk after each utterance."""

    index: int
    t: float
    score: float
    tier: str


class TimelineResponse(BaseModel):
    """Risk over time plus the final assessment."""

    points: list[TimelinePoint]
    final: RiskAssessment


@router.post(
    "/conversation/timeline", response_model=TimelineResponse, summary="Risk after every utterance"
)
async def timeline(
    req: AssessRequest, svc: Svc, caller: Caller, ai: bool = True
) -> TimelineResponse:
    """Shows how early the conversation alone becomes suspicious (no payment context per step)."""
    points: list[TimelinePoint] = []
    for i in range(len(req.transcript)):
        part = AssessRequest(profile=req.profile, transcript=req.transcript[: i + 1])
        a = svc.engine.assess(part)
        points.append(
            TimelinePoint(index=i, t=req.transcript[i].t, score=a.score, tier=a.tier.value)
        )
    final = await svc.assess(req, use_ai=ai)
    _audit("timeline", caller, final, turns=len(req.transcript))
    return TimelineResponse(points=points, final=final)


class TurnIn(BaseModel):
    """One new utterance in a live session."""

    speaker: Speaker
    text: str = Field(max_length=2000)
    t: float = Field(ge=0)
    language: Language = Language.EN
    senior: bool = False
    txn: TransactionContext | None = None


class TurnOut(BaseModel):
    """Assessment after the new turn."""

    turns: int
    assessment: RiskAssessment


@router.post(
    "/sessions/{sid}/turns", response_model=TurnOut, summary="Add a turn to a live session"
)
async def add_turn(
    sid: SessionId, body: TurnIn, svc: Svc, caller: Caller, ai: bool = True
) -> TurnOut:
    """Server-side session so clients can stream utterances. Sessions expire and can be erased."""
    sess = svc.sessions.get_or_create(f"{caller}:{sid}", body.language, body.senior)
    if len(sess.utterances) >= 200:
        raise HTTPException(409, "Session is full; start a new one.")
    sess.utterances.append(Utterance(speaker=body.speaker, text=body.text, t=body.t))
    req = AssessRequest(
        profile=UserProfile(
            user_id=re.sub(r"\W", "", sid)[:32],
            preferred_language=body.language,
            senior=body.senior,
        ),
        transcript=list(sess.utterances),
        txn=body.txn,
    )
    a = await svc.assess(req, use_ai=ai)
    _audit("session_turn", caller, a, turns=len(sess.utterances))
    return TurnOut(turns=len(sess.utterances), assessment=a)


@router.delete("/sessions/{sid}", status_code=204, summary="Erase a session")
async def delete_session(sid: SessionId, svc: Svc, caller: Caller) -> None:
    """Erases the stored conversation immediately."""
    svc.sessions.delete(f"{caller}:{sid}")


@router.get("/demo/calls", summary="Fictional demo calls")
async def demo_calls() -> list[dict[str, object]]:
    """Scripted calls (English, Hindi/Hinglish, Telugu) used by the UI."""
    return [
        {
            **{k: v for k, v in c.items() if k not in {"turns", "language"}},
            "language": c["language"].value,
            "turns": [{"speaker": s, "text": t, "t": x} for s, t, x in c["turns"]],
        }
        for c in DEMO_CALLS
    ]
