# SPDX-License-Identifier: Apache-2.0
"""Guardrails for payments made by AI agents on a user's behalf.

Modelled on the *ideas* in Google's Agent Payments Protocol (AP2): a user-signed
**intent mandate** (what the agent may buy, how much, until when) and a
merchant-signed **cart mandate** bound to that intent by hash. This module is
AP2-inspired, **not** a certified implementation of the AP2 specification; it
shows the checks an issuer or wallet should run before honouring an agent's
payment, and adds fraud-oriented checks (gift cards, price spikes, replay,
prompt-injection text in cart metadata, intent drift).
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import threading
import time
from collections.abc import Callable
from typing import Any, Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from pydantic import BaseModel, Field

from vigil.domain.models import Category
from vigil.risk.lexicon import ENTRIES, normalize

HIGH_RISK_CATEGORIES = frozenset(
    {"gift_card", "prepaid_card", "crypto", "money_transfer", "forex", "wallet_topup"}
)


class IntentMandate(BaseModel):
    """What the user authorised the agent to do."""

    mandate_id: str
    user_id: str
    agent_id: str
    description: str = Field(max_length=500)
    max_amount_inr: float = Field(gt=0)
    allowed_categories: list[str]
    allowed_merchants: list[str] | None = None
    expires_at: float
    nonce: str
    allow_high_risk_categories: bool = False


class CartItem(BaseModel):
    """One line of a cart."""

    sku: str
    title: str = Field(max_length=200)
    category: str
    unit_price_inr: float = Field(gt=0)
    qty: int = Field(ge=1, le=100)


class CartMandate(BaseModel):
    """What the merchant is asking to be paid for."""

    cart_id: str
    intent_hash: str
    merchant_id: str
    items: list[CartItem]
    total_inr: float
    created_at: float
    nonce: str
    notes: str = Field("", max_length=500)


class SignedMandate(BaseModel):
    """A mandate payload with a detached Ed25519 signature."""

    payload: dict[str, Any]
    signature: str
    signer: str


def canonical(payload: dict[str, Any]) -> bytes:
    """Canonical JSON bytes used for hashing and signing."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def payload_hash(payload: dict[str, Any]) -> str:
    """SHA-256 hex digest of the canonical payload."""
    return hashlib.sha256(canonical(payload)).hexdigest()


class Signer:
    """Holds an Ed25519 key; used by wallets/merchants (and by tests and demos)."""

    def __init__(self, signer_id: str, key: Ed25519PrivateKey | None = None) -> None:
        """Creates a signer, generating a key if none is given."""
        self.signer_id = signer_id
        self._key = key or Ed25519PrivateKey.generate()

    @property
    def public_key(self) -> Ed25519PublicKey:
        """The verification key."""
        return self._key.public_key()

    def sign(self, model: BaseModel) -> SignedMandate:
        """Signs a mandate model."""
        payload = json.loads(model.model_dump_json())
        sig = base64.b64encode(self._key.sign(canonical(payload))).decode()
        return SignedMandate(payload=payload, signature=sig, signer=self.signer_id)


class KeyRegistry:
    """Maps signer IDs to public keys (a stand-in for a wallet/merchant PKI)."""

    def __init__(self) -> None:
        """Creates an empty registry."""
        self._keys: dict[str, Ed25519PublicKey] = {}

    def register(self, signer_id: str, key: Ed25519PublicKey) -> None:
        """Registers a public key."""
        self._keys[signer_id] = key

    def verify(self, m: SignedMandate) -> bool:
        """Returns True if the signature is valid for a registered signer."""
        key = self._keys.get(m.signer)
        if key is None:
            return False
        try:
            key.verify(base64.b64decode(m.signature), canonical(m.payload))
        except (InvalidSignature, ValueError):
            return False
        return True


class Check(BaseModel):
    """Outcome of one check."""

    name: str
    passed: bool
    severity: Literal["hard", "soft"]
    detail: str


class Verdict(BaseModel):
    """Result of verifying an agent payment."""

    decision: Literal["approve", "step_up", "deny"]
    risk_score: float = Field(ge=0, le=1)
    checks: list[Check]
    reasons: list[str]


_WEIGHTS = {"hard": 0.9, "soft": 0.45}
_STOP = frozenset(
    [
        "a",
        "an",
        "the",
        "for",
        "of",
        "to",
        "and",
        "or",
        "in",
        "on",
        "with",
        "my",
        "me",
        "i",
        "buy",
        "get",
        "under",
        "below",
        "within",
        "some",
    ]
)
_INJECTION = [e.pattern for e in ENTRIES if e.category is Category.INJECTION]


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOP and len(t) > 2}


class MandateGuard:
    """Verifies cart/intent pairs before an agent's payment is honoured."""

    def __init__(
        self,
        registry: KeyRegistry,
        clock: Callable[[], float] = time.time,
        reference_prices: dict[str, float] | None = None,
        hourly_cap_inr: float = 200_000,
    ) -> None:
        """Creates a guard.

        Args:
            registry: Public keys of users' wallets and merchants.
            clock: Injectable clock.
            reference_prices: Typical price per category, for spike detection.
            hourly_cap_inr: Max total an agent may spend per hour.
        """
        self._registry = registry
        self._clock = clock
        self._ref = reference_prices or {}
        self._cap = hourly_cap_inr
        self._seen: set[str] = set()
        self._spend: list[tuple[float, str, float]] = []
        self._lock = threading.Lock()

    def verify(
        self, intent_signed: SignedMandate, cart_signed: SignedMandate, agent_id: str
    ) -> Verdict:
        """Runs all checks and returns a verdict."""
        checks: list[Check] = []

        def add(name: str, ok: bool, sev: Literal["hard", "soft"], detail: str) -> None:
            checks.append(Check(name=name, passed=ok, severity=sev, detail=detail))

        sig_i, sig_c = self._registry.verify(intent_signed), self._registry.verify(cart_signed)
        add(
            "intent_signature",
            sig_i,
            "hard",
            "User wallet signature valid"
            if sig_i
            else "Intent signature invalid or signer unknown",
        )
        add(
            "cart_signature",
            sig_c,
            "hard",
            "Merchant signature valid" if sig_c else "Cart signature invalid or signer unknown",
        )
        try:
            intent = IntentMandate.model_validate(intent_signed.payload)
            cart = CartMandate.model_validate(cart_signed.payload)
        except ValueError as e:
            add("well_formed", False, "hard", f"Malformed mandate: {str(e)[:120]}")
            return self._finish(checks)

        now = self._clock()
        add(
            "not_expired",
            intent.expires_at > now,
            "hard",
            "Intent still valid" if intent.expires_at > now else "Intent expired",
        )
        bound = cart.intent_hash == payload_hash(intent_signed.payload)
        add(
            "cart_bound_to_intent",
            bound,
            "hard",
            "Cart references this exact intent" if bound else "Cart is not bound to this intent",
        )
        add(
            "agent_identity",
            intent.agent_id == agent_id,
            "hard",
            "Caller is the authorised agent"
            if intent.agent_id == agent_id
            else f"Caller {agent_id!r} is not the authorised agent",
        )
        total = round(sum(i.unit_price_inr * i.qty for i in cart.items), 2)
        add(
            "total_matches_items",
            abs(total - cart.total_inr) < 0.01,
            "hard",
            f"Items sum to ₹{total:,.2f}, cart says ₹{cart.total_inr:,.2f}",
        )
        add(
            "within_cap",
            cart.total_inr <= intent.max_amount_inr,
            "hard",
            f"₹{cart.total_inr:,.2f} vs cap ₹{intent.max_amount_inr:,.2f}",
        )
        if intent.allowed_merchants is not None:
            ok = cart.merchant_id in intent.allowed_merchants
            add(
                "merchant_allowed",
                ok,
                "hard",
                "Merchant on allow-list" if ok else f"Merchant {cart.merchant_id!r} not authorised",
            )
        bad_cat = sorted({i.category for i in cart.items} - set(intent.allowed_categories))
        add(
            "categories_allowed",
            not bad_cat,
            "hard",
            "All items in authorised categories"
            if not bad_cat
            else f"Unauthorised categories: {', '.join(bad_cat)}",
        )
        risky = sorted({i.category for i in cart.items} & HIGH_RISK_CATEGORIES)
        add(
            "no_high_risk_items",
            not risky or intent.allow_high_risk_categories,
            "soft",
            "No gift-card / crypto / transfer items"
            if not risky
            else f"High-risk items: {', '.join(risky)} (agents are a common vector for gift-card scams)",
        )
        spikes = [
            i.title
            for i in cart.items
            if self._ref.get(i.category) and i.unit_price_inr > 3 * self._ref[i.category]
        ]
        add(
            "price_reasonable",
            not spikes,
            "soft",
            "Prices in normal range"
            if not spikes
            else f"Price far above normal: {', '.join(spikes)[:80]}",
        )
        overlap = self._intent_overlap(intent.description, cart)
        add("matches_intent", overlap >= 0.15, "soft", f"Cart/intent word overlap {overlap:.0%}")
        text = normalize(" ".join([cart.notes, *[i.title for i in cart.items]]))
        injected = any(p.search(text) for p in _INJECTION)
        add(
            "no_instruction_text",
            not injected,
            "hard",
            "No instruction-like text in cart"
            if not injected
            else "Cart text tries to instruct the AI (possible prompt injection)",
        )

        with self._lock:
            replay = cart.nonce in self._seen or intent.nonce + cart.cart_id in self._seen
            hour_spend = sum(a for t, ag, a in self._spend if ag == agent_id and now - t < 3600)
        add(
            "no_replay",
            not replay,
            "hard",
            "Fresh nonce" if not replay else "Mandate/cart already used",
        )
        add(
            "hourly_velocity",
            hour_spend + cart.total_inr <= self._cap,
            "soft",
            f"Agent spent ₹{hour_spend:,.0f} in the last hour; cap ₹{self._cap:,.0f}",
        )

        verdict = self._finish(checks)
        if verdict.decision == "approve":
            with self._lock:
                self._seen.update({cart.nonce, intent.nonce + cart.cart_id})
                self._spend.append((now, agent_id, cart.total_inr))
        return verdict

    @staticmethod
    def _intent_overlap(description: str, cart: CartMandate) -> float:
        want = _tokens(description)
        have = _tokens(" ".join(i.title + " " + i.category.replace("_", " ") for i in cart.items))
        return len(want & have) / len(want) if want else 1.0

    @staticmethod
    def _finish(checks: list[Check]) -> Verdict:
        failed = [c for c in checks if not c.passed]
        keep = 1.0
        for c in failed:
            keep *= 1 - _WEIGHTS[c.severity]
        hard = any(c.severity == "hard" for c in failed)
        decision: Literal["approve", "step_up", "deny"] = (
            "deny" if hard else ("step_up" if failed else "approve")
        )
        return Verdict(
            decision=decision,
            risk_score=round(1 - keep, 3),
            checks=checks,
            reasons=[c.detail for c in failed],
        )
