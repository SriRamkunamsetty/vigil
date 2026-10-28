# SPDX-License-Identifier: Apache-2.0
"""Evaluation metrics."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import numpy as np


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a proportion."""
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, centre - half), min(1.0, centre + half)


def average_precision(scores: Sequence[float], labels: Sequence[int]) -> float:
    """Area under the precision-recall curve (average precision)."""
    s = np.asarray(scores, dtype=float)
    y = np.asarray(labels, dtype=float)
    if y.sum() == 0:
        return 0.0
    order = np.argsort(-s, kind="stable")
    y = y[order]
    tp = np.cumsum(y)
    precision = tp / (np.arange(len(y)) + 1)
    return float((precision * y).sum() / y.sum())


def confusion(pred: Sequence[bool], labels: Sequence[int]) -> dict[str, Any]:
    """Precision/recall/FPR with Wilson intervals for recall and FPR."""
    tp = sum(1 for p, y in zip(pred, labels, strict=True) if p and y)
    fp = sum(1 for p, y in zip(pred, labels, strict=True) if p and not y)
    fn = sum(1 for p, y in zip(pred, labels, strict=True) if not p and y)
    tn = sum(1 for p, y in zip(pred, labels, strict=True) if not p and not y)
    rec = tp / (tp + fn) if tp + fn else 0.0
    fpr = fp / (fp + tn) if fp + tn else 0.0
    prec = tp / (tp + fp) if tp + fp else 0.0
    rlo, rhi = wilson(tp, tp + fn)
    flo, fhi = wilson(fp, fp + tn)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": prec,
        "recall": rec,
        "fpr": fpr,
        "recall_ci": [rlo, rhi],
        "fpr_ci": [flo, fhi],
        "f1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0,
    }


def precision_at_prevalence(recall: float, fpr: float, prevalence: float) -> float:
    """Expected precision if scams were ``prevalence`` of traffic."""
    num = recall * prevalence
    den = num + fpr * (1 - prevalence)
    return num / den if den else 0.0
