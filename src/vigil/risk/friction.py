# SPDX-License-Identifier: Apache-2.0
"""Maps a risk probability to a proportionate, reversible friction tier."""

from __future__ import annotations

import math
from dataclasses import dataclass

from vigil.domain.models import (
    Actions,
    ScamType,
    Tier,
    TransactionContext,
    UserProfile,
)


@dataclass(frozen=True)
class Thresholds:
    """Probability cut-offs for each tier."""

    nudge: float = 0.25
    friction: float = 0.50
    hold: float = 0.80


def thresholds_for(txn: TransactionContext | None, profile: UserProfile) -> Thresholds:
    """Returns thresholds adjusted for exposure.

    Higher amounts and users who opted in to extra protection get earlier
    friction. The adjustment only ever adds *protection*; it is never used to
    deny service, and every tier above ``nudge`` has a human recourse path.
    """
    t = Thresholds()
    shift = 0.0
    if txn is not None:
        if txn.amount_inr >= 200_000:
            shift += 0.10
        elif txn.amount_inr >= 50_000:
            shift += 0.05
    if profile.senior:
        shift += 0.05
    return Thresholds(
        nudge=max(0.15, t.nudge - shift / 2),
        friction=max(0.35, t.friction - shift),
        hold=max(0.65, t.hold - shift),
    )


def decide(probability: float, has_txn: bool, thr: Thresholds) -> Tier:
    """Chooses a tier. ``HOLD`` is only possible when a payment is pending."""
    if probability >= thr.hold:
        return Tier.HOLD if has_txn else Tier.FRICTION
    if probability >= thr.friction:
        return Tier.FRICTION
    if probability >= thr.nudge:
        return Tier.NUDGE
    return Tier.ALLOW


def actions_for(
    tier: Tier,
    txn: TransactionContext | None,
    profile: UserProfile,
    scam_type: ScamType,
    probability: float,
) -> Actions:
    """Returns the concrete actions for a tier."""
    if tier is Tier.ALLOW or tier is Tier.NUDGE:
        return Actions()
    delay = 0
    if txn is not None and tier is Tier.FRICTION:
        delay = int(min(900, max(60, 30 * math.sqrt(txn.amount_inr / 1000))))
    coercive = scam_type in {
        ScamType.DIGITAL_ARREST,
        ScamType.KYC_OTP,
        ScamType.REMOTE_ACCESS,
    }
    return Actions(
        delay_seconds=delay,
        hold_for_review=tier is Tier.HOLD,
        require_verified_callback=tier is Tier.HOLD or coercive,
        offer_trusted_contact_alert=profile.trusted_contact_opted_in,
        show_helpline_1930=probability >= 0.5,
    )
