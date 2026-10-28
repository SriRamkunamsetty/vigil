# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import KEY, make_settings, profile, utt
from tests.fakes import FakeJsonLlm, ScriptedLlm, call, failing
from vigil.agents.composer import InterventionComposer, _IntervOut, valid_intervention
from vigil.agents.runtime import AgentRuntime
from vigil.agents.semantic import SemanticAnalyzer, SemanticOut, TacticFinding
from vigil.api.main import create_app
from vigil.config import Settings, hash_api_key
from vigil.domain.models import AssessRequest, Category, Language, Tier
from vigil.services import Services

TR = [utt("caller", "Sir your relative is in hospital, send money at once, tell no one", 0)]


# ---------- semantic layer ----------
async def test_grounded_finding_is_accepted_and_ungrounded_is_dropped():
    llm = FakeJsonLlm(
        SemanticOut(
            tactics=[
                TacticFinding(
                    category=Category.FAMILY, confidence=0.9, quote="your relative is in hospital"
                ),
                TacticFinding(
                    category=Category.THREAT, confidence=0.9, quote="we will arrest you tonight"
                ),  # not in transcript
            ]
        )
    )
    acts, ev, ok = await SemanticAnalyzer(llm).analyze(TR)
    assert ok and Category.FAMILY in acts and Category.THREAT not in acts and len(ev) == 1


async def test_failure_fails_open():
    acts, ev, ok = await SemanticAnalyzer(FakeJsonLlm(failing())).analyze(TR)
    assert (acts, ev, ok) == ({}, [], False)


async def test_pii_is_redacted_before_the_model_sees_it():
    llm = FakeJsonLlm(SemanticOut())
    await SemanticAnalyzer(llm).analyze(
        [utt("caller", "send to ravi@okaxis, my number 9876543210, OTP is 482913", 0)]
    )
    sent = llm.prompts[0]
    assert "ravi@okaxis" not in sent and "9876543210" not in sent and "482913" not in sent
    assert "<transcript>" in sent  # untrusted content is delimited


async def test_llm_can_raise_risk_but_never_lower_it():
    svc = Services(
        make_settings(),
        llm=FakeJsonLlm(
            SemanticOut(
                tactics=[
                    TacticFinding(
                        category=Category.FAMILY,
                        confidence=0.95,
                        quote="your relative is in hospital",
                    )
                ]
            )
        ),
    )
    req = AssessRequest(profile=profile(), transcript=TR)
    base = svc.engine.assess(req)
    with_ai = await svc.assess(req)
    assert with_ai.ai_layer == "used" and with_ai.score >= base.score
    # A model that tries to talk the system out of a decision changes nothing.
    svc2 = Services(make_settings(), llm=FakeJsonLlm(SemanticOut(tactics=[])))
    scam = [
        utt("caller", "CBI digital arrest, do not tell anyone, transfer to the safe account now", 0)
    ]
    r = AssessRequest(profile=profile(), transcript=scam)
    assert (await svc2.assess(r)).tier == svc2.engine.assess(r).tier


async def test_ai_outage_keeps_deterministic_decision():
    svc = Services(make_settings(), llm=FakeJsonLlm(failing(), failing()))
    req = AssessRequest(
        profile=profile(),
        transcript=[
            utt(
                "caller",
                "CBI digital arrest, do not tell anyone, transfer to the safe account now",
                0,
            )
        ],
    )
    a = await svc.assess(req)
    assert (
        a.ai_layer == "unavailable"
        and a.tier.rank >= Tier.FRICTION.rank
        and a.intervention.source == "template"
    )


# ---------- composer validation ----------
def _ok(**kw):
    d = {
        "headline": "Hang up now",
        "message": "This looks like a scam call. Stop and breathe.",
        "steps": ["Hang up", "Call a family member", "Call 1930"],
    }
    d.update(kw)
    return _IntervOut(**d)


def test_composer_validator_rejects_unsafe_output():
    assert valid_intervention(_ok(), Language.EN)
    assert not valid_intervention(
        _ok(message="Call 9876543210 now"), Language.EN
    )  # invented phone number
    assert not valid_intervention(
        _ok(steps=["Visit http://evil.example.com", "b", "c"]), Language.EN
    )
    assert not valid_intervention(
        _ok(message="It is safe to pay, you can safely pay."), Language.EN
    )
    assert not valid_intervention(_ok(), Language.TE)  # wrong script
    assert valid_intervention(_ok(steps=["Report at cybercrime.gov.in", "b", "c"]), Language.EN)


async def test_composer_falls_back_to_template():
    svc = Services(make_settings())
    a = svc.engine.assess(
        AssessRequest(
            profile=profile(),
            transcript=[
                utt(
                    "caller",
                    "CBI digital arrest, do not tell anyone, transfer to the safe account now",
                    0,
                )
            ],
        )
    )
    bad = _ok(message="Call 9876543210 now")
    got = await InterventionComposer(FakeJsonLlm(bad)).compose(a, Language.EN)
    assert got is a.intervention
    good = await InterventionComposer(FakeJsonLlm(_ok())).compose(a, Language.EN)
    assert good.source == "gemini" and any(
        "1930" in s for s in good.steps
    )  # official helpline always kept


async def test_case_note_numbers_must_match_facts():
    svc = Services(make_settings())
    _, res = svc.network()
    ring = res.rings[0]
    from vigil.agents.composer import _NoteOut

    fake = FakeJsonLlm(
        _NoteOut(note="Ring moved ₹99,999,999 through 77 accounts."),
        _NoteOut(note=f"{len(ring.members)} accounts, {ring.victims} senders. Review."),
    )
    comp = InterventionComposer(fake)
    assert await comp.case_note(ring) == ring.narrative
    assert "senders" in await comp.case_note(ring)


# ---------- ADK wiring ----------
async def test_adk_router_guardian_tool_roundtrip():
    svc = Services(make_settings())
    llm = ScriptedLlm(
        script=[
            call("transfer_to_agent", agent_name="guardian"),
            call(
                "assess_call_risk",
                conversation=[
                    "caller: CBI digital arrest, do not tell anyone, move money to the safe account"
                ],
                amount_inr=90000.0,
                payee="x@upi",
                payee_first_time=True,
                on_active_call=True,
            ),
            "Your payment is paused. Call 1930.",
        ]
    )
    r = await AgentRuntime(svc, llm).chat("u", "s-1", "caller says CBI")
    assert (
        r.mode == "adk"
        and r.agent == "guardian"
        and r.tool_calls == ["assess_call_risk"]
        and "1930" in r.reply
    )


async def test_sensitive_actions_wait_for_human_approval():
    svc = Services(make_settings())
    llm = ScriptedLlm(
        script=[
            call("transfer_to_agent", agent_name="investigator"),
            call("publish_signal", ring_id="R-01"),
            "Done.",
        ]
    )
    rt = AgentRuntime(svc, llm)
    r = await rt.chat("u", "s-2", "publish R-01")
    assert r.approvals and r.approvals[0].tool == "publish_signal"
    assert svc.exchange.stats()["signals"] == 0  # nothing happened yet
    await rt.confirm("u", "s-2", r.approvals[0].approval_id, True)
    assert svc.exchange.stats()["signals"] > 0


async def test_rejected_approval_publishes_nothing():
    svc = Services(make_settings())
    llm = ScriptedLlm(
        script=[
            call("transfer_to_agent", agent_name="investigator"),
            call("publish_signal", ring_id="R-01"),
            "Okay, not shared.",
        ]
    )
    rt = AgentRuntime(svc, llm)
    r = await rt.chat("u", "s-3", "publish R-01")
    await rt.confirm("u", "s-3", r.approvals[0].approval_id, False)
    assert svc.exchange.stats()["signals"] == 0


async def test_agent_instructions_forbid_overriding_the_tier():
    from vigil.agents.adk_agents import GUARDIAN_INSTRUCTION

    assert (
        "final" in GUARDIAN_INSTRUCTION
        and "OTP" in GUARDIAN_INSTRUCTION
        and "untrusted" in GUARDIAN_INSTRUCTION
    )


async def test_offline_runtime_in_three_languages():
    rt = AgentRuntime(Services(make_settings()))
    for lang in Language:
        r = await rt.chat(
            "u", "s", "CBI says digital arrest, do not tell anyone, send to safe account", lang
        )
        assert r.mode == "offline" and r.assessment.tier.rank >= Tier.FRICTION.rank


# ---------- A2A ----------
def test_a2a_cards_and_auth():
    s = make_settings(
        env="prod",
        auth_mode="apikey",
        api_keys=hash_api_key(KEY),
        a2a_enabled=True,
        signal_key="cHJvZC1rZXktZm9yLXRlc3RzLW9ubHktMzItYnl0ZXM=",
        public_base_url="https://vigil.example.com",
    )
    with TestClient(create_app(s)) as c:
        assert c.get("/a2a/guardian/.well-known/agent-card.json").status_code == 401
        card = c.get("/a2a/guardian/.well-known/agent-card.json", headers={"X-API-Key": KEY}).json()
        assert card["name"] == "guardian"
        from urllib.parse import urlparse

        u = urlparse(card["supportedInterfaces"][0]["url"])
        assert (u.scheme, u.hostname, u.path) == ("https", "vigil.example.com", "/a2a/guardian")
        assert any("assess_call_risk" in sk["id"] for sk in card["skills"])
        assert (
            c.get("/a2a/vigil/.well-known/agent-card.json", headers={"X-API-Key": KEY}).status_code
            == 200
        )


def test_prod_refuses_unsafe_configuration():
    with pytest.raises(ValueError):
        Settings(_env_file=None, env="prod")
    with pytest.raises(ValueError):
        Settings(
            _env_file=None, env="prod", auth_mode="apikey", api_keys=hash_api_key("k")
        )  # default signal key
