# SPDX-License-Identifier: Apache-2.0
"""Runtime configuration, loaded from ``VIGIL_*`` environment variables."""

from __future__ import annotations

import base64
import functools
import hashlib
from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Fixed development key so local runs and tests are reproducible. Production
# refuses to start with it (see ``Settings._check_prod``).
_DEV_SIGNAL_KEY = base64.b64encode(b"vigil-dev-only-consortium-key-32").decode()


class Settings(BaseSettings):
    """Application settings.

    Attributes:
        env: Deployment environment. ``prod`` enforces authentication; ``demo`` is a public
            showcase that serves synthetic data only (open routes, strict limits).
        auth_mode: ``demo`` leaves demo routes open (dev only); ``apikey``
            requires ``X-API-Key`` matching one of ``api_keys``.
        api_keys: Comma-separated SHA-256 hex digests of accepted API keys.
        llm_enabled: Use Gemini (Vertex AI) for explanations and chat. The
            risk decision never depends on it.
    """

    model_config = SettingsConfigDict(env_prefix="VIGIL_", env_file=".env", extra="ignore")

    env: Literal["dev", "demo", "prod"] = "dev"
    auth_mode: Literal["demo", "apikey"] = "demo"
    api_keys: str = ""
    cors_origins: str = ""
    rate_limit_per_min: int = 120
    max_body_bytes: int = 256_000
    trusted_proxy_hops: int = 0  # Cloud Run: 1 (client IP is the last X-Forwarded-For entry)
    public_base_url: str = "http://localhost:8080"  # advertised in A2A agent cards
    a2a_enabled: bool = True

    llm_enabled: bool = False
    llm_timeout_s: float = 8.0
    model_reasoning: str = "gemini-3.5-flash"
    model_fast: str = "gemini-3.1-flash-lite"
    model_live: str = "gemini-3.1-flash-live-preview"

    signal_key: str = _DEV_SIGNAL_KEY
    signal_min_reporters: int = 2
    signal_ttl_days: int = 30

    session_ttl_s: int = 3600
    max_sessions: int = 10_000

    @property
    def api_key_digests(self) -> frozenset[str]:
        """Accepted API key digests, lower-cased."""
        return frozenset(k.strip().lower() for k in self.api_keys.split(",") if k.strip())

    @property
    def cors_origin_list(self) -> list[str]:
        """Allowed CORS origins."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _check_prod(self) -> Self:
        if self.env == "prod":
            if self.auth_mode != "apikey" or not self.api_key_digests:
                raise ValueError("prod requires VIGIL_AUTH_MODE=apikey and VIGIL_API_KEYS")
            if self.signal_key == _DEV_SIGNAL_KEY:
                raise ValueError("prod requires a non-default VIGIL_SIGNAL_KEY")
        return self


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Returns the cached process-wide settings."""
    return Settings()


def hash_api_key(key: str) -> str:
    """Returns the SHA-256 hex digest used to store API keys."""
    return hashlib.sha256(key.encode()).hexdigest()
