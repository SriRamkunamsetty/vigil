# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import pytest

from vigil.network.exchange import BloomFilter, RateLimited, SignalExchange, normalize_identifier
from vigil.network.graph import MuleNetworkAnalyzer
from vigil.synthetic.network import generate_network


@pytest.fixture(scope="module")
def result():
    net = generate_network(n_accounts=800, n_rings=5, seed=21)
    return net, MuleNetworkAnalyzer().analyze(net.transfers, net.accounts)


def test_finds_mules_and_spares_lookalikes(result):
    net, res = result
    flagged = {a for a, n in res.nodes.items() if n.score >= 0.5}
    assert len(flagged & net.mules) / len(net.mules) > 0.9
    assert len(flagged - net.mules) <= 2
    assert not (flagged & net.hard_negatives), "merchants/payroll/charity must not be flagged"


def test_rings_have_explanations_and_numbers_add_up(result):
    _, res = result
    assert len(res.rings) >= 4
    r = res.rings[0]
    assert r.victims > 0 and r.exposure_inr > 0 and r.entry_accounts and r.cashout_accounts
    assert "human approval" in r.narrative
    n = res.nodes[r.members[0]]
    assert n.reasons and 0 <= n.score <= 1


# ---- exchange ----
class Clock:
    t = 1_000_000.0

    def __call__(self) -> float:
        return self.t


def make(clock=None, **kw):
    return SignalExchange(b"k" * 32, clock=clock or Clock(), **kw)


def test_needs_two_banks_to_corroborate():
    x = make()
    x.publish("bank-a", "payee", "Scam@UPI")
    one = x.lookup("payee", "scam@upi ")  # normalisation: case and spaces
    assert one.flag == 0.6 and not one.corroborated
    x.publish("bank-a", "payee", "scam@upi")  # same bank again does not corroborate
    assert not x.lookup("payee", "scam@upi").corroborated
    x.publish("bank-b", "payee", "scam@upi")
    two = x.lookup("payee", "scam@upi")
    assert two.flag == 1.0 and two.corroborated and two.reporters == 2


def test_ttl_retract_and_rate_limit():
    c = Clock()
    x = make(c, ttl_days=1, max_publishes_per_hour=3)
    x.publish("a", "payee", "p1")
    x.publish("b", "payee", "p1")
    assert x.lookup("payee", "p1").corroborated
    assert x.retract("b", "payee", "p1") and not x.lookup("payee", "p1").corroborated
    c.t += 2 * 86400
    assert x.lookup("payee", "p1").flag == 0  # expired
    for i in range(3):
        x.publish("spam", "payee", f"q{i}")
    with pytest.raises(RateLimited):
        x.publish("spam", "payee", "q9")


def test_tokens_do_not_reveal_identifiers_and_depend_on_key():
    a, b = make().token("payee", "x@upi"), SignalExchange(b"z" * 32).token("payee", "x@upi")
    assert "x@upi" not in a and len(a) == 64 and a != b
    assert normalize_identifier("phone", "+91 98765-43210") == "9876543210"
    with pytest.raises(ValueError):
        make().token("nope", "x")


def test_bloom_has_no_false_negatives_and_low_false_positives():
    bf = BloomFilter(2000, 0.01)
    toks = [f"t{i}" for i in range(2000)]
    for t in toks:
        bf.add(t)
    assert all(t in bf for t in toks)
    fp = sum(f"other{i}" in bf for i in range(5000)) / 5000
    assert fp < 0.03


def test_exported_bloom_contains_only_corroborated():
    x = make()
    x.publish("a", "payee", "one")
    x.publish("a", "payee", "two")
    x.publish("b", "payee", "two")
    bf = x.export_bloom()
    assert x.token("payee", "two") in bf and x.token("payee", "one") not in bf
