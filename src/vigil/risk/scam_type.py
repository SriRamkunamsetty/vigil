# SPDX-License-Identifier: Apache-2.0
"""Names the most likely scam typology from tactic activations."""

from __future__ import annotations

from vigil.domain.models import Category as C
from vigil.domain.models import ScamType


def classify(act: dict[C, float]) -> tuple[ScamType, float]:
    """Returns (typology, confidence) given tactic activations.

    Confidence is the separation between the best and second-best typology, not
    the probability that a scam is happening (that is the risk score).
    """

    def a(c: C) -> float:
        return act.get(c, 0.0)

    scores = {
        ScamType.DIGITAL_ARREST: 0.35 * a(C.THREAT)
        + 0.30 * a(C.AUTHORITY)
        + 0.20 * a(C.SECRECY)
        + 0.15 * a(C.SAFE_ACCOUNT),
        ScamType.COURIER_CUSTOMS: 0.55 * a(C.COURIER) + 0.15 * a(C.AUTHORITY) + 0.10 * a(C.THREAT),
        ScamType.KYC_OTP: 0.40 * a(C.KYC_BLOCK) + 0.35 * a(C.CREDENTIAL) + 0.15 * a(C.BANK_CLAIM),
        ScamType.REMOTE_ACCESS: 0.65 * a(C.REMOTE_ACCESS) + 0.10 * a(C.BANK_CLAIM),
        ScamType.INVESTMENT: 0.80 * a(C.INVESTMENT),
        ScamType.PRIZE_REFUND: 0.75 * a(C.PRIZE_REFUND) + 0.10 * a(C.CREDENTIAL),
        ScamType.FAMILY_EMERGENCY: 0.75 * a(C.FAMILY) + 0.10 * a(C.URGENCY),
    }
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    (best, s1), (_, s2) = ranked[0], ranked[1]
    if s1 < 0.22:
        return ScamType.NONE, 0.0
    return best, round(s1 / (s1 + s2 + 0.1), 3)
