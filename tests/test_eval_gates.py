# SPDX-License-Identifier: Apache-2.0
"""Regression gates on the offline evaluation (synthetic data; relative claims only)."""

from __future__ import annotations

import pytest

from vigil.eval.run import evaluate_conversations, evaluate_exchange, evaluate_network


@pytest.fixture(scope="module")
def conv():
    return evaluate_conversations(n=2500)


def system(conv, name):
    return next(s for s in conv["systems"] if s["system"] == name)


def test_fusion_beats_each_single_signal_at_friction_level(conv):
    fused = system(conv, "Vigil fused")["friction"]
    for other in (
        "Static rule: ≥₹50k to first-time payee",
        "Transaction signals only (what a bank sees today)",
        "Conversation only (no payment context)",
    ):
        assert fused["recall"] > system(conv, other)["friction"]["recall"], other
    assert fused["fpr"] < 0.03 and fused["precision"] > 0.9


def test_hard_negatives_mostly_quiet(conv):
    quiet = {
        "bank_advisory",
        "bank_care_genuine",
        "advisor_sip",
        "insurance_premium",
        "delivery_cod",
        "plain_payment",
    }
    for k, v in conv["benign_friction_by_kind"].items():
        if k in quiet:
            assert v["friction_or_hold_rate"] < 0.01, k


def test_known_weakness_is_reported_not_hidden(conv):
    w = conv["fused_recall_by_wording_family"]
    assert w["unseen"]["recall"] < w["seen"]["recall"]  # the gap exists and is surfaced in the UI


def test_latency_budget(conv):
    assert conv["latency_ms"]["p95"] < 25


def test_exchange_and_network():
    ex = evaluate_exchange(1500)
    assert (
        ex["with_exchange"]["recall"] > ex["without_exchange"]["recall"]
        and ex["with_exchange"]["fpr"] <= ex["without_exchange"]["fpr"] + 0.01
    )
    n = evaluate_network()
    v = n["rules"]["Vigil network score ≥ 0.5"]
    assert v["precision"] > 0.9 and v["recall"] > 0.9
    assert v["precision"] > n["rules"]["fan-in ≥ 8 senders"]["precision"]
