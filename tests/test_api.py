# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from tests.conftest import KEY


def _arrest_req(with_txn: bool = True) -> dict:
    req = {
        "profile": {"user_id": "u1", "preferred_language": "en", "senior": True},
        "transcript": [
            {
                "speaker": "caller",
                "text": "This is the CBI. You are under digital arrest. Do not tell anyone.",
                "t": 0,
            },
            {
                "speaker": "caller",
                "text": "Transfer your savings to the RBI safe account immediately or we arrest you.",
                "t": 10,
            },
        ],
    }
    if with_txn:
        req["txn"] = {
            "amount_inr": 150000,
            "payee_ref": "safe@bank",
            "payee_first_time": True,
            "active_call_with_unknown_number": True,
            "call_duration_s": 1800,
        }
    return req


def test_health_and_meta(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    r = client.get("/readyz").json()
    assert r["status"] == "ready" and r["agents"] == "offline"
    m = client.get("/v1/meta").json()
    assert m["languages"] == ["en", "hi", "te"] and "synthetic" in m["data"]


def test_assess_holds_arrest_scam(client):
    r = client.post("/v1/assess", json=_arrest_req())
    assert r.status_code == 200
    body = r.json()
    assert body["tier"] == "hold" and body["scam_type"] == "digital_arrest"
    assert body["actions"]["hold_for_review"] is True
    assert body["intervention"]["steps"] and body["drivers"]
    assert (
        r.headers["x-content-type-options"] == "nosniff"
        and r.headers["cache-control"] == "no-store"
    )
    assert r.headers["x-request-id"]


def test_assess_benign_is_allowed(client):
    req = {
        "profile": {"user_id": "u1"},
        "transcript": [
            {"speaker": "caller", "text": "Hi, are we still on for dinner at 8?", "t": 0}
        ],
        "txn": {"amount_inr": 900, "payee_ref": "friend@upi"},
    }
    assert client.post("/v1/assess", json=req).json()["tier"] == "allow"


def test_validation_error_is_problem_json_and_does_not_echo_input(client):
    r = client.post(
        "/v1/assess",
        json={"profile": {"user_id": "u1"}, "txn": {"amount_inr": -5, "payee_ref": "SECRET-PAYEE"}},
    )
    assert r.status_code == 422 and r.headers["content-type"].startswith("application/problem+json")
    assert "SECRET-PAYEE" not in r.text


def test_timeline_is_monotone_enough(client):
    r = client.post("/v1/conversation/timeline", json=_arrest_req(False)).json()
    assert len(r["points"]) == 2 and r["points"][-1]["score"] >= r["points"][0]["score"]
    assert r["final"]["tier"] in {"friction", "nudge"}


def test_session_turns_and_erase(client):
    sid = "session-abc123"
    a = client.post(
        f"/v1/sessions/{sid}/turns",
        json={
            "speaker": "caller",
            "text": "This is the police, you are under arrest",
            "t": 0,
            "senior": True,
        },
    )
    assert a.status_code == 200 and a.json()["turns"] == 1
    b = client.post(
        f"/v1/sessions/{sid}/turns",
        json={
            "speaker": "caller",
            "text": "Do not tell anyone, move money to the safe account",
            "t": 8,
            "senior": True,
        },
    )
    assert (
        b.json()["turns"] == 2 and b.json()["assessment"]["score"] > a.json()["assessment"]["score"]
    )
    assert client.delete(f"/v1/sessions/{sid}").status_code == 204
    c = client.post(f"/v1/sessions/{sid}/turns", json={"speaker": "user", "text": "hello", "t": 0})
    assert c.json()["turns"] == 1  # erased then restarted
    assert (
        client.post(
            "/v1/sessions/x/turns", json={"speaker": "user", "text": "hi", "t": 0}
        ).status_code
        == 422
    )


def test_demo_calls_behave(client):
    calls = client.get("/v1/demo/calls").json()
    assert {c["id"] for c in calls} == {
        "digital_arrest_en",
        "kyc_hi",
        "investment_te",
        "genuine_bank",
    }
    for c in calls:
        req = {
            "profile": {
                "user_id": "demo",
                "preferred_language": c["language"],
                "senior": c["senior"],
            },
            "transcript": c["turns"],
            "txn": c["txn"],
        }
        tier = client.post("/v1/assess", json=req).json()["tier"]
        if c["id"] == "genuine_bank":
            assert tier == "allow"
        else:
            assert tier in {"friction", "hold"}, (c["id"], tier)


def test_network_and_human_approved_publish(client):
    rings = client.get("/v1/network/rings").json()
    assert rings["rings"] and rings["flagged_accounts"] > 0
    rid = rings["rings"][0]["ring_id"]
    detail = client.get(f"/v1/network/rings/{rid}").json()
    assert detail["case_note"] and detail["nodes"] and detail["edges"]
    assert (
        client.post(
            f"/v1/network/rings/{rid}/publish", json={"approved": False, "analyst": "asha"}
        ).status_code
        == 400
    )
    ok = client.post(
        f"/v1/network/rings/{rid}/publish",
        json={"approved": True, "analyst": "asha"},
        headers={"X-Demo-Institution": "bank-a"},
    )
    assert ok.status_code == 200 and ok.json()["published"] > 0
    assert client.get("/v1/network/rings/R-99").status_code == 404
    assert client.get("/v1/network/rings/bad").status_code == 422


def test_network_effect_via_signals(client):
    payee = "scammer.collect@upi"
    first = client.post("/v1/signals/lookup", json={"kind": "payee", "identifier": payee}).json()
    assert first["flag"] == 0
    client.post(
        "/v1/signals/publish",
        json={"kind": "payee", "identifier": payee},
        headers={"X-Demo-Institution": "bank-a"},
    )
    one = client.post("/v1/signals/lookup", json={"kind": "payee", "identifier": payee}).json()
    assert one["flag"] == 0.6 and one["corroborated"] is False
    client.post(
        "/v1/signals/publish",
        json={"kind": "payee", "identifier": payee},
        headers={"X-Demo-Institution": "bank-b"},
    )
    two = client.post("/v1/signals/lookup", json={"kind": "payee", "identifier": payee}).json()
    assert two["flag"] == 1.0 and two["corroborated"] is True and "reporters" in two
    # the flag now raises risk for a customer of a third bank
    req = {
        "profile": {"user_id": "u9"},
        "txn": {"amount_inr": 20000, "payee_ref": payee, "payee_first_time": True},
    }
    assert client.post("/v1/assess", json=req).json()["tier"] in {"friction", "hold"}
    bloom = client.get("/v1/signals/bloom").json()
    assert bloom["m_bits"] > 0 and bloom["bits_b64"]
    assert client.post(
        "/v1/signals/retract",
        json={"kind": "payee", "identifier": payee},
        headers={"X-Demo-Institution": "bank-b"},
    ).json() == {"retracted": True}
    assert (
        client.post("/v1/signals/lookup", json={"kind": "payee", "identifier": payee}).json()[
            "corroborated"
        ]
        is False
    )


def test_agent_payment_cases(client):
    cases = client.get("/v1/agent-payments/cases").json()
    assert len(cases) == 7
    for c in cases:
        r = client.post("/v1/agent-payments/verify-demo", json={"case_id": c["case_id"]}).json()
        assert r["verdict"]["decision"] == c["expected"], c["case_id"]
    assert (
        client.post("/v1/agent-payments/verify-demo", json={"case_id": "nope_x"}).status_code == 404
    )


def test_offline_chat_uses_rule_engine(client):
    r = client.post(
        "/v1/agents/chat",
        json={
            "session_id": "chat-123456",
            "message": "A man says he is CBI and I am under digital arrest, do not tell anyone, send money to the safe account",
        },
    ).json()
    assert (
        r["mode"] == "offline"
        and r["agent"] == "guardian"
        and r["assessment"]["tier"] in {"friction", "hold"}
    )


def test_auth_required_in_apikey_mode(secure_client):
    assert secure_client.get("/healthz").status_code == 200
    assert secure_client.post("/v1/assess", json=_arrest_req()).status_code == 401
    assert (
        secure_client.post(
            "/v1/assess", json=_arrest_req(), headers={"X-API-Key": "wrong"}
        ).status_code
        == 401
    )
    ok = secure_client.post("/v1/assess", json=_arrest_req(), headers={"X-API-Key": KEY})
    assert ok.status_code == 200 and ok.headers["x-request-id"]
    assert secure_client.get("/docs").status_code == 404  # no docs in prod


def test_rate_limit_and_body_limit(secure_client):
    h = {"X-API-Key": KEY}
    codes = [secure_client.get("/v1/meta", headers=h).status_code for _ in range(8)]
    assert codes.count(429) >= 2 and codes[0] == 200
    r = secure_client.get("/v1/meta", headers=h)
    assert r.status_code == 429 and "retry-after" in r.headers


def test_body_too_large(client):
    big = {
        "profile": {"user_id": "u1"},
        "transcript": [{"speaker": "caller", "text": "x" * 1900, "t": i} for i in range(150)],
    }
    assert client.post("/v1/assess", json=big).status_code == 413
