# SPDX-License-Identifier: Apache-2.0
"""Fitting and calibration utilities for adapting Vigil to an institution's data."""

from __future__ import annotations

import itertools
import math

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


def fit_logistic(
    x: FloatArray,
    y: FloatArray,
    prior_w: FloatArray | None = None,
    prior_b: float = 0.0,
    l2: float = 1.0,
    iters: int = 300,
) -> tuple[FloatArray, float]:
    """Fits an L2-regularised logistic regression anchored at prior weights.

    Regularising towards the hand-set priors (rather than zero) keeps sensible,
    explainable weights when labelled data is scarce.

    Args:
        x: Feature matrix, shape (n, d).
        y: Labels in {0, 1}, shape (n,).
        prior_w: Prior weights, shape (d,). Defaults to zeros.
        prior_b: Prior bias.
        l2: Strength of the pull towards the prior.
        iters: Newton-Raphson iterations.

    Returns:
        (weights, bias).
    """
    n, d = x.shape
    w0 = np.zeros(d) if prior_w is None else prior_w.astype(np.float64)
    beta = np.concatenate([w0, [prior_b]])
    prior = beta.copy()
    xb = np.hstack([x, np.ones((n, 1))])
    reg = np.eye(d + 1) * l2
    reg[-1, -1] = 1e-6
    for _ in range(iters):
        z = np.clip(xb @ beta, -30, 30)
        p = 1 / (1 + np.exp(-z))
        grad = xb.T @ (p - y) + l2 * (beta - prior) * (np.arange(d + 1) < d)
        hess = (xb * (p * (1 - p))[:, None]).T @ xb + reg
        step = np.linalg.solve(hess, grad)
        beta -= step
        if float(np.max(np.abs(step))) < 1e-8:
            break
    return beta[:-1], float(beta[-1])


def prevalence_shift(logit: float, train_prevalence: float, true_prevalence: float) -> float:
    """Corrects a log-odds score trained at one prevalence for another.

    Fraud is rare in production; models trained on balanced data over-predict
    unless this offset (log prior-odds ratio) is applied.
    """

    def lo(p: float) -> float:
        return math.log(p / (1 - p))

    return logit + lo(true_prevalence) - lo(train_prevalence)


def expected_calibration_error(p: FloatArray, y: FloatArray, bins: int = 10) -> float:
    """Expected calibration error with equal-width bins."""
    edges = np.linspace(0, 1, bins + 1)
    ece = 0.0
    for lo, hi in itertools.pairwise(edges):
        mask = (p >= lo) & (p < hi if hi < 1 else p <= hi)
        if mask.any():
            ece += mask.mean() * abs(float(p[mask].mean()) - float(y[mask].mean()))
    return float(ece)
