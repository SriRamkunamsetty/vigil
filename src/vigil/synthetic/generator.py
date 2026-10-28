# SPDX-License-Identifier: Apache-2.0
"""Seeded generator of labelled scam / benign scenarios (conversation + payment)."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from vigil.domain.models import (
    Language,
    ScamType,
    Speaker,
    TransactionContext,
    UserProfile,
    Utterance,
)
from vigil.synthetic import scenarios as sc

LANG_WEIGHTS = {"en": 0.35, "hinglish": 0.20, "hi": 0.20, "te": 0.25}
PROFILE_LANG = {"en": Language.EN, "hinglish": Language.HI, "hi": Language.HI, "te": Language.TE}


@dataclass
class Scenario:
    """One labelled situation ending in a payment."""

    sid: str
    label: int  # 1 = the payment is scam-induced
    kind: str  # scam type value or benign kind
    language: str
    family: str  # seen | unseen | benign
    profile: UserProfile
    transcript: list[Utterance]
    txn: TransactionContext
    payment_t: float
    meta: dict[str, str] = field(default_factory=dict)


def _fmt_inr(x: float) -> str:
    n = int(round(x, -2)) or int(x)
    s = f"{n:,}"
    # Indian digit grouping
    if n >= 1000:
        head, tail = str(n)[:-3], str(n)[-3:]
        parts: list[str] = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join([*parts, tail])
    return f"₹{s}"


def _typo(text: str, rng: random.Random) -> str:
    if any(ord(c) > 0x2FF for c in text):
        return text
    words = text.split(" ")
    idx = [i for i, w in enumerate(words) if len(w) >= 6 and w.isalpha()]
    for i in rng.sample(idx, k=min(len(idx), rng.choice([1, 2]))):
        w = words[i]
        j = rng.randrange(1, len(w) - 1)
        words[i] = w[:j] + w[j + 1 :]
    return " ".join(words)


def _pick_lang(rng: random.Random) -> str:
    return rng.choices(list(LANG_WEIGHTS), weights=list(LANG_WEIGHTS.values()))[0]


def _lognormal(rng: random.Random, median: float, sigma: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, median * math.exp(rng.gauss(0, sigma))))


def _vpa(rng: random.Random, scam: bool) -> str:
    handle = rng.choice(["okaxis", "ybl", "oksbi", "paytm", "ibl", "upi"])
    stem = (
        rng.choice(["rbi.verify", "cbi.clear", "kyc.help", "gift.win", "fund.alpha"])
        if scam
        else rng.choice(["ravi", "priya", "shop", "rent", "mohan", "anita"])
    )
    return f"{stem}{rng.randrange(1000, 99999)}@{handle}"


def _profile(rng: random.Random, language: str) -> UserProfile:
    avg = _lognormal(rng, 1200, 0.8, 200, 40000)
    lang = PROFILE_LANG[language] if rng.random() > 0.1 else rng.choice(list(Language))
    return UserProfile(
        user_id=f"u{rng.randrange(10**8):08d}",
        preferred_language=lang,
        senior=rng.random() < 0.15,
        trusted_contact_opted_in=rng.random() < 0.4,
        avg_txn_inr=round(avg, 2),
        max_txn_30d_inr=round(avg * rng.uniform(3, 12), 2),
    )


def _scam_txn(rng: random.Random, stype: ScamType, payee: str) -> TransactionContext:
    coercive = stype in {
        ScamType.DIGITAL_ARREST,
        ScamType.COURIER_CUSTOMS,
        ScamType.KYC_OTP,
        ScamType.REMOTE_ACCESS,
    }
    on_call = rng.random() < (0.8 if coercive else 0.3)
    return TransactionContext(
        amount_inr=round(_lognormal(rng, 60000, 0.9, 2000, 2_500_000), 2),
        payee_ref=payee,
        payee_first_time=rng.random() < 0.92,
        payee_account_age_days=rng.choice([None, 2, 6, 14, 25, 45, 120, 400]),
        payee_is_merchant=rng.random() < 0.03,
        hour_of_day=rng.choice([rng.randrange(8, 22)] * 4 + [rng.randrange(0, 24)]),
        device_new=rng.random() < 0.15,
        sim_swap_recent=rng.random() < 0.05,
        active_call_with_unknown_number=on_call,
        call_duration_s=rng.uniform(300, 3600) if on_call else 0.0,
        screen_sharing_active=rng.random()
        < (0.35 if stype in {ScamType.REMOTE_ACCESS, ScamType.KYC_OTP} else 0.03),
        txn_count_last_hour=rng.choice([0, 0, 1, 1, 2, 3, 4]),
    )


def _benign_txn(rng: random.Random, kind: str, payee: str) -> TransactionContext:
    amount = {
        "landlord_rent": lambda: _lognormal(rng, 22000, 0.4, 5000, 80000),
        "used_car": lambda: _lognormal(rng, 250000, 0.5, 50000, 900000),
        "family_real": lambda: _lognormal(rng, 20000, 0.7, 2000, 150000),
        "friend_split": lambda: _lognormal(rng, 900, 0.6, 100, 6000),
        "delivery_cod": lambda: _lognormal(rng, 900, 0.8, 100, 12000),
        "insurance_premium": lambda: _lognormal(rng, 12000, 0.6, 1500, 60000),
        "advisor_sip": lambda: _lognormal(rng, 5000, 0.4, 1000, 25000),
    }.get(kind, lambda: _lognormal(rng, 1500, 1.0, 20, 60000))()
    on_call = rng.random() < {
        "used_car": 0.7,
        "family_real": 0.5,
        "landlord_rent": 0.3,
        "delivery_cod": 0.1,
    }.get(kind, 0.05)
    first = rng.random() < {
        "landlord_rent": 0.6,
        "used_car": 0.95,
        "delivery_cod": 0.7,
        "friend_split": 0.1,
        "family_real": 0.05,
    }.get(kind, 0.2)
    return TransactionContext(
        amount_inr=round(amount, 2),
        payee_ref=payee,
        payee_first_time=first,
        payee_account_age_days=rng.choice([None, None, 90, 365, 1200, 20]),
        payee_is_merchant=rng.random()
        < (0.9 if kind in {"insurance_premium", "delivery_cod", "advisor_sip"} else 0.3),
        hour_of_day=rng.choice([rng.randrange(8, 22)] * 5 + [rng.randrange(0, 24)]),
        device_new=rng.random() < 0.04,
        sim_swap_recent=rng.random() < 0.01,
        active_call_with_unknown_number=on_call,
        call_duration_s=rng.uniform(60, 1500) if on_call else 0.0,
        screen_sharing_active=rng.random() < 0.01,
        txn_count_last_hour=rng.choice([0, 0, 0, 1, 1, 2]),
    )


def _times(rng: random.Random, n: int) -> list[float]:
    t, out = rng.uniform(3, 10), []
    for _ in range(n):
        out.append(round(t, 1))
        t += rng.uniform(10, 40)
    return out


def generate(
    n: int,
    seed: int,
    scam_rate: float = 0.35,
    unseen_rate: float = 0.35,
    transcript_available: float = 0.85,
    scam_payee_pool: int | None = None,
) -> list[Scenario]:
    """Generates ``n`` labelled scenarios deterministically from ``seed``.

    Args:
        n: Number of scenarios.
        seed: RNG seed.
        scam_rate: Fraction that are scams (kept high for evaluation power;
            reported metrics are re-weighted to realistic prevalence).
        unseen_rate: Fraction of scams using the held-out paraphrase family.
        transcript_available: Fraction of scams where a transcript exists.
        scam_payee_pool: If set, scam payees are drawn from a pool of this size,
            so the same collector account receives many victims (as mule
            accounts do). ``None`` makes every scam payee unique.
    """
    rng = random.Random(seed)
    pool = [_vpa(rng, True) for _ in range(scam_payee_pool)] if scam_payee_pool else None
    out: list[Scenario] = []
    benign_kinds = [*sc.BENIGN, "plain_payment"]
    benign_w = [*[sc.BENIGN_WEIGHTS[k] for k in sc.BENIGN], 4.0]
    for i in range(n):
        lang = _pick_lang(rng)
        profile = _profile(rng, lang)
        if rng.random() < scam_rate:
            stype = rng.choice(list(sc.SCAMS))
            family = "unseen" if rng.random() < unseen_rate else "seen"
            txn = _scam_txn(rng, stype, rng.choice(pool) if pool else _vpa(rng, True))
            slots = {
                "name": rng.choice(sc.NAMES),
                "org": rng.choice(sc.ORGS),
                "bank": rng.choice(sc.BANKS),
                "amt": _fmt_inr(txn.amount_inr),
            }
            beats = [b.format(**slots) for b in sc.SCAMS[stype][lang][family]]
            if len(beats) > 2 and rng.random() < 0.2:
                del beats[rng.randrange(0, len(beats) - 1)]
            has_t = rng.random() < transcript_available
            turns: list[tuple[Speaker, str]] = []
            for j, b in enumerate(beats):
                turns.append((Speaker.CALLER, _typo(b, rng) if rng.random() < 0.15 else b))
                if j < len(beats) - 1 and rng.random() < 0.5:
                    turns.append((Speaker.USER, rng.choice(sc.FILLER_USER[lang])))
            label, kind = 1, stype.value
        else:
            bk = rng.choices(benign_kinds, weights=benign_w)[0]
            family, label, kind = "benign", 0, bk
            txn = _benign_txn(rng, bk, _vpa(rng, False))
            has_t = bk != "plain_payment"
            turns = []
            if has_t:
                variants = sc.BENIGN[bk]
                blang = (
                    lang
                    if lang in variants
                    else ("en" if "en" in variants else next(iter(variants)))
                )
                slots = {"amt": _fmt_inr(txn.amount_inr)}
                turns = [(Speaker(s), t.format(**slots)) for s, t in variants[blang]]
        if not has_t:
            turns = []
        ts = _times(rng, len(turns))
        transcript = [
            Utterance(speaker=s, text=t, t=tt) for (s, t), tt in zip(turns, ts, strict=True)
        ]
        payment_t = (ts[-1] + rng.uniform(15, 40)) if ts else 0.0
        out.append(
            Scenario(
                sid=f"s{seed}-{i:05d}",
                label=label,
                kind=kind,
                language=lang,
                family=family,
                profile=profile,
                transcript=transcript,
                txn=txn,
                payment_t=round(payment_t, 1),
                meta={"has_transcript": str(bool(transcript))},
            )
        )
    return out
