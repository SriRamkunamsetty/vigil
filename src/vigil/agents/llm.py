# SPDX-License-Identifier: Apache-2.0
"""Thin, testable wrapper around Gemini (Vertex AI or Gemini API) for JSON output."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Raised when the model call fails, times out or returns invalid output."""


class JsonLLM(Protocol):
    """Anything that can return schema-validated JSON for a prompt."""

    async def generate_json(self, *, system: str, prompt: str, schema: type[T]) -> T:
        """Returns a validated ``schema`` instance or raises :class:`LLMError`."""
        ...


class GeminiJsonClient:
    """Calls Gemini through the ``google-genai`` SDK.

    Authentication follows the SDK's standard environment variables:
    ``GOOGLE_GENAI_USE_VERTEXAI``, ``GOOGLE_CLOUD_PROJECT``,
    ``GOOGLE_CLOUD_LOCATION`` (Vertex AI with Application Default Credentials,
    the recommended production path) or ``GOOGLE_API_KEY``.
    """

    def __init__(
        self, model: str, timeout_s: float = 8.0, model_armor_template: str | None = None
    ) -> None:
        """Creates the client lazily so import never needs credentials.

        Args:
            model: Gemini model ID.
            timeout_s: Hard per-call timeout.
            model_armor_template: Optional Model Armor template resource name to
                screen prompts/responses for injection and unsafe content.
        """
        self._model = model
        self._timeout = timeout_s
        self._armor = model_armor_template or os.environ.get("VIGIL_MODEL_ARMOR_TEMPLATE")
        self._client: object | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            from google import genai

            self._client = genai.Client()
        return self._client

    async def generate_json(self, *, system: str, prompt: str, schema: type[T]) -> T:
        """Generates and validates JSON; never returns unvalidated output."""
        from google.genai import types

        cfg: dict[str, object] = {
            "system_instruction": system,
            "response_mime_type": "application/json",
            "response_schema": schema,
            "temperature": 0.0,
            "max_output_tokens": 1024,
        }
        if self._armor:
            cfg["model_armor_config"] = types.ModelArmorConfig(
                prompt_template_name=self._armor, response_template_name=self._armor
            )
        try:
            client = self._get_client()
            resp = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=self._model, contents=prompt, config=types.GenerateContentConfig(**cfg)
                ),
                timeout=self._timeout,
            )
            return schema.model_validate_json(resp.text or "")
        except Exception as e:
            log.warning("llm_call_failed", extra={"error": type(e).__name__, "model": self._model})
            raise LLMError(type(e).__name__) from e
