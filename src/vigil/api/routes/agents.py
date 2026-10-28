# SPDX-License-Identifier: Apache-2.0
"""Conversational agent endpoints (ADK)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from vigil.agents.runtime import ChatReply
from vigil.api.deps import Caller, Runtime
from vigil.domain.models import Language
from vigil.obs import audit_logger

router = APIRouter(prefix="/v1/agents", tags=["agents"])
_SID = r"^[A-Za-z0-9_-]{6,64}$"


class ChatIn(BaseModel):
    """A chat message."""

    session_id: str = Field(pattern=_SID)
    message: str = Field(min_length=1, max_length=2000)
    language: Language = Language.EN


@router.post("/chat", response_model=ChatReply, summary="Talk to the Vigil agents")
async def chat(body: ChatIn, rt: Runtime, caller: Caller) -> ChatReply:
    """Routes to guardian / investigator / payment_guard. Offline mode is rule-based."""
    r = await rt.chat(caller, body.session_id, body.message, body.language)
    audit_logger.info(
        "agent_chat",
        extra={"caller": caller, "agent": r.agent, "mode": r.mode, "tools": r.tool_calls},
    )
    return r


class ConfirmIn(BaseModel):
    """A human's answer to an approval request."""

    session_id: str = Field(pattern=_SID)
    approval_id: str = Field(min_length=4, max_length=128)
    approved: bool


@router.post("/confirm", response_model=ChatReply, summary="Approve or reject a pending action")
async def confirm(body: ConfirmIn, rt: Runtime, caller: Caller) -> ChatReply:
    """Actions such as notifying a trusted contact or publishing signals wait here."""
    r = await rt.confirm(caller, body.session_id, body.approval_id, body.approved)
    audit_logger.info("agent_confirm", extra={"caller": caller, "approved": body.approved})
    return r
