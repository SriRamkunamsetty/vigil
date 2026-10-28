# SPDX-License-Identifier: Apache-2.0
"""Scripted fakes so agent wiring is tested without network or credentials."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from google.adk.models import BaseLlm, LlmResponse
from google.adk.models.llm_request import LlmRequest
from google.genai import types
from pydantic import BaseModel

from vigil.agents.llm import LLMError


class ScriptedLlm(BaseLlm):
    """Plays back responses; each item is a ``types.Part`` list or a plain string."""

    model: str = "scripted"
    script: list[Any] = []
    calls: list[Any] = []

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        self.calls.append(llm_request)
        item = self.script.pop(0) if self.script else "(no more script)"
        parts = [types.Part(text=item)] if isinstance(item, str) else item
        yield LlmResponse(content=types.Content(role="model", parts=parts))


def call(name: str, **args: Any) -> list[types.Part]:
    """A model turn that calls a tool."""
    return [types.Part(function_call=types.FunctionCall(name=name, args=args))]


class FakeJsonLlm:
    """JsonLLM returning canned objects (or raising) for the semantic/composer tests."""

    def __init__(self, *outputs: BaseModel | Exception) -> None:
        self.outputs = list(outputs)
        self.prompts: list[str] = []

    async def generate_json(self, *, system: str, prompt: str, schema: type[Any]) -> Any:
        self.prompts.append(prompt)
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


def failing() -> LLMError:
    return LLMError("boom")
