# SPDX-License-Identifier: Apache-2.0
"""Transaction and device context features (each in [0, 1])."""

from __future__ import annotations

import math

from vigil.domain.models import TransactionContext, UserProfile


def _clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def behaviour_features(
    profile: UserProfile, txn: TransactionContext, network_flag: float
) -> dict[str, float]:
    """Builds behavioural features for one payment.

    Args:
        profile: The payer's minimal profile.
        txn: The payment context.
        network_flag: Cross-bank signal about the payee: 0 none, 0.6 reported by
            one institution, 1.0 corroborated by several.

    Returns:
        Feature name -> activation in [0, 1].
    """
    baseline = max(profile.max_txn_30d_inr, profile.avg_txn_inr * 3.0, 1000.0)
    ratio = txn.amount_inr / baseline
    amount_ratio = _clip(math.log2(max(ratio, 1e-9)) / 4.0)
    large_abs = _clip((math.log10(txn.amount_inr) - 4.0) / 1.3)

    age = txn.payee_account_age_days
    young = 0.0
    if age is not None:
        young = 1.0 if age < 30 else 0.5 if age < 90 else 0.0

    night = 1.0 if txn.hour_of_day < 6 else 0.5 if txn.hour_of_day >= 22 else 0.0
    return {
        "amount_ratio": amount_ratio,
        "large_absolute": large_abs,
        "new_payee": 1.0 if txn.payee_first_time else 0.0,
        "young_payee_account": young,
        "network_flag": network_flag,
        "active_call": 1.0 if txn.active_call_with_unknown_number else 0.0,
        "long_call": _clip(txn.call_duration_s / 1200.0),
        "screen_sharing": 1.0 if txn.screen_sharing_active else 0.0,
        "new_device": 1.0 if txn.device_new else 0.0,
        "sim_swap": 1.0 if txn.sim_swap_recent else 0.0,
        "night": night,
        "velocity": _clip((txn.txn_count_last_hour - 1) / 4.0),
        "merchant": 1.0 if txn.payee_is_merchant else 0.0,
    }
