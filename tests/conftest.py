# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from vigil.api.main import create_app
from vigil.config import Settings, hash_api_key
from vigil.domain.models import Language, Speaker, UserProfile, Utterance


def make_settings(**kw: object) -> Settings:
    base: dict[str, object] = {
        "env": "dev",
        "auth_mode": "demo",
        "llm_enabled": False,
        "a2a_enabled": False,
    }
    base.update(kw)
    return Settings(_env_file=None, **base)  # type: ignore[arg-type]


@pytest.fixture
def client():
    with TestClient(create_app(make_settings())) as c:
        yield c


KEY = "test-key-123"


@pytest.fixture
def secure_client():
    s = make_settings(
        env="prod",
        auth_mode="apikey",
        api_keys=hash_api_key(KEY),
        signal_key="cHJvZC1rZXktZm9yLXRlc3RzLW9ubHktMzItYnl0ZXM=",
        rate_limit_per_min=5,
    )
    with TestClient(create_app(s)) as c:
        yield c


def utt(speaker: str, text: str, t: float = 0.0) -> Utterance:
    return Utterance(speaker=Speaker(speaker), text=text, t=t)


def profile(lang: Language = Language.EN, **kw: object) -> UserProfile:
    return UserProfile(user_id="u-test", preferred_language=lang, **kw)  # type: ignore[arg-type]
