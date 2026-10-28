# SPDX-License-Identifier: Apache-2.0
"""Runs the ADK agent system, or a deterministic offline guardian when no LLM is configured.

The offline mode keeps the demo, tests and judges' laptops working without
credentials: it calls the same risk engine and returns the same safe steps, it
just does not hold a free-form conversation.
"""

from __future__ import annotations

import logging
import uuid
from typing import Literal

from google.adk.agents import LlmAgent
from google.adk.agents.context_cache_config import ContextCacheConfig
from google.adk.apps import App
from google.adk.models import BaseLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel, Field

from vigil.agents.adk_agents import build_agents
from vigil.domain.models import (
    AssessRequest,
    Language,
    RiskAssessment,
    Speaker,
    UserProfile,
    Utterance,
)
from vigil.services import Services

log = logging.getLogger(__name__)
APP_NAME = "vigil"
_CONFIRM = "adk_request_confirmation"


class Approval(BaseModel):
    """An action waiting for the human's yes/no."""

    approval_id: str
    tool: str
    args: dict[str, object] = Field(default_factory=dict)


class ChatReply(BaseModel):
    """Result of one chat turn."""

    reply: str
    agent: str
    mode: Literal["adk", "offline"]
    tool_calls: list[str] = Field(default_factory=list)
    approvals: list[Approval] = Field(default_factory=list)
    assessment: RiskAssessment | None = None


_OFFLINE_NOTE = {
    Language.EN: "I'm running without the AI assistant right now, so this is the rule-based safety check.",
    Language.HI: "अभी AI सहायक चालू नहीं है, इसलिए यह नियम-आधारित सुरक्षा जाँच है।",
    Language.TE: "ఇప్పుడు AI సహాయకుడు అందుబాటులో లేదు, కాబట్టి ఇది నియమాల ఆధారిత భద్రతా తనిఖీ.",
}
_ALL_CLEAR = {
    Language.EN: "I don't see clear scam signs in what you wrote. Still, never share OTPs or PINs, and call your bank on its official number if unsure.",
    Language.HI: "आपके लिखे में मुझे साफ़ ठगी के संकेत नहीं दिखे। फिर भी OTP या PIN कभी साझा न करें, और शक हो तो बैंक के आधिकारिक नंबर पर फ़ोन करें।",
    Language.TE: "మీరు రాసినదాంట్లో స్పష్టమైన మోసపు సంకేతాలు కనిపించలేదు. అయినా OTP లేదా PIN ఎవరికీ చెప్పకండి, సందేహం ఉంటే బ్యాంక్ అధికారిక నంబర్‌కు ఫోన్ చేయండి.",
}


class AgentRuntime:
    """Chat entry point used by the API."""

    def __init__(self, svc: Services, model: str | BaseLlm | None = None) -> None:
        """Creates the runtime.

        Args:
            svc: Shared services.
            model: Force ADK mode with this model (tests pass a fake). When
                ``None``, ADK mode is used only if ``VIGIL_LLM_ENABLED`` is set.
        """
        self._svc = svc
        self.root: LlmAgent = build_agents(svc, model)
        self._use_adk = model is not None or svc.settings.llm_enabled
        self._sessions = InMemorySessionService()
        # Each transfer between agents changes the prompt prefix, so give the app a context cache.
        app = App(
            name=APP_NAME,
            root_agent=self.root,
            context_cache_config=ContextCacheConfig(min_tokens=2048),
        )
        self._runner = Runner(app=app, session_service=self._sessions, auto_create_session=True)

    @property
    def mode(self) -> Literal["adk", "offline"]:
        """Current mode."""
        return "adk" if self._use_adk else "offline"

    async def chat(
        self, user_id: str, session_id: str, text: str, language: Language = Language.EN
    ) -> ChatReply:
        """Handles one user message."""
        if not self._use_adk:
            return await self._offline(text, language)
        return await self._run(
            user_id, session_id, types.Content(role="user", parts=[types.Part(text=text)])
        )

    async def confirm(
        self, user_id: str, session_id: str, approval_id: str, approved: bool
    ) -> ChatReply:
        """Answers a pending human-approval request."""
        if not self._use_adk:
            return ChatReply(reply="No pending approvals.", agent="vigil", mode="offline")
        part = types.Part(
            function_response=types.FunctionResponse(
                id=approval_id, name=_CONFIRM, response={"confirmed": approved}
            )
        )
        return await self._run(user_id, session_id, types.Content(role="user", parts=[part]))

    async def _run(self, user_id: str, session_id: str, content: types.Content) -> ChatReply:
        texts: list[str] = []
        calls: list[str] = []
        approvals: list[Approval] = []
        last_agent = "vigil"
        async for ev in self._runner.run_async(
            user_id=user_id, session_id=session_id, new_message=content
        ):
            if not ev.content or not ev.content.parts:
                continue
            for p in ev.content.parts:
                if p.function_call:
                    fc = p.function_call
                    if fc.name == _CONFIRM:
                        orig = (fc.args or {}).get("originalFunctionCall", {}) or {}
                        approvals.append(
                            Approval(
                                approval_id=fc.id or uuid.uuid4().hex,
                                tool=str(orig.get("name", "?")),
                                args=dict(orig.get("args", {}) or {}),
                            )
                        )
                    elif fc.name and not fc.name.startswith("transfer_to_agent"):
                        calls.append(fc.name)
                elif p.text and not ev.partial and ev.author != "user":
                    texts.append(p.text)
                    last_agent = ev.author
        reply = (
            texts[-1].strip()
            if texts
            else ("I need your approval to continue." if approvals else "")
        )
        return ChatReply(
            reply=reply, agent=last_agent, mode="adk", tool_calls=calls, approvals=approvals
        )

    async def _offline(self, text: str, language: Language) -> ChatReply:
        req = AssessRequest(
            profile=UserProfile(user_id="offline-chat", preferred_language=language),
            transcript=[Utterance(speaker=Speaker.CALLER, text=text[:2000], t=0.0)],
        )
        a = await self._svc.assess(req, use_ai=False)
        iv = a.intervention
        if iv is None or a.tier.value == "allow":
            body = _ALL_CLEAR[language]
        else:
            body = f"{iv.headline}\n{iv.message}\n" + "\n".join(
                f"{i}. {s}" for i, s in enumerate(iv.steps, 1)
            )
        return ChatReply(
            reply=f"{body}\n\n({_OFFLINE_NOTE[language]})",
            agent="guardian",
            mode="offline",
            tool_calls=["assess_call_risk"],
            assessment=a,
        )
