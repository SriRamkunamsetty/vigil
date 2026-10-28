# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import pytest

from vigil.payments.demo import AgentPaymentDemo
from vigil.payments.mandate import MandateGuard, payload_hash

DEMO = AgentPaymentDemo(clock=1_800_000_000.0)


@pytest.mark.parametrize("cid", list(DEMO.cases))
def test_each_case_gets_the_expected_decision(cid):
    case, v = DEMO.run_case(cid)
    assert v.decision == case.expected, (cid, v.reasons)


def failed(cid):
    return {c.name for c in DEMO.run_case(cid)[1].checks if not c.passed}


def test_the_right_check_fails_for_each_attack():
    assert "within_cap" in failed("over_cap")
    assert "no_instruction_text" in failed("hijack")
    assert "cart_signature" in failed("tampered")
    assert "agent_identity" in failed("wrong_agent")
    assert "no_replay" in failed("replay")


def test_step_up_is_not_a_denial_and_never_silently_approves():
    _, v = DEMO.run_case("gift_step_up")
    assert v.decision == "step_up" and all(c.passed for c in v.checks if c.severity == "hard")


def test_expiry_and_hourly_velocity():
    case = DEMO.cases["legit"]
    late = MandateGuard(DEMO.registry, clock=lambda: DEMO.now + 7200)
    assert late.verify(case.intent, case.cart, case.agent_id).decision == "deny"
    tight = MandateGuard(DEMO.registry, clock=lambda: DEMO.now, hourly_cap_inr=1000)
    assert tight.verify(case.intent, case.cart, case.agent_id).decision != "approve"


def test_payload_hash_is_order_independent():
    assert payload_hash({"a": 1, "b": [1, 2]}) == payload_hash({"b": [1, 2], "a": 1})
