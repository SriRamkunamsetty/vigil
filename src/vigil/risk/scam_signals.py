# SPDX-License-Identifier: Apache-2.0
"""Detects social-engineering tactics in a call/chat transcript."""

from __future__ import annotations

import functools
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from vigil.domain.models import Category, Evidence, Language, Speaker, Utterance
from vigil.risk.lexicon import (
    ENTRIES,
    NEGATION_SENSITIVE,
    is_credential_advisory,
    is_negated,
    normalize,
)

# How much each speaker's words count towards a tactic. The user's own words
# describe what the caller said, so they count less; the user *asking* to pay is
# never evidence of a scam.
_USER_MULT: dict[Category, float] = {
    Category.PAYMENT: 0.0,
    Category.FAMILY: 0.3,
    Category.URGENCY: 0.3,
    Category.BANK_CLAIM: 0.3,
}
_DEFAULT_USER_MULT = 0.6

_HINGLISH = frozenset(
    [
        "hai",
        "hain",
        "karo",
        "kijiye",
        "aap",
        "aapka",
        "aapki",
        "kya",
        "nahi",
        "bhej",
        "bhejo",
        "paise",
        "batao",
        "bataiye",
        "turant",
        "ghar",
        "jaldi",
        "hoon",
        "sahab",
        "wapas",
        "khata",
        "mein",
        "liye",
        "raha",
        "rahi",
        "madad",
        "dijiye",
        "boliye",
        "bolo",
    ]
)
_TENGLISH = frozenset(
    [
        "cheyandi",
        "cheppandi",
        "evariki",
        "dabbulu",
        "pampandi",
        "ventane",
        "meeru",
        "enti",
        "ledu",
        "chestam",
        "avutundi",
        "cheyakandi",
        "ippude",
        "nenu",
        "mee",
        "kosam",
        "ayyindi",
        "vachindi",
        "pettandi",
        "cheyyi",
    ]
)
_WORD = re.compile(r"[a-z]+")


def detect_language(text: str) -> Language:
    """Guesses the language of one utterance from script and romanised markers."""
    dev = sum(1 for ch in text if "ऀ" <= ch <= "ॿ")
    tel = sum(1 for ch in text if "ఀ" <= ch <= "౿")
    if dev > 2 and dev >= tel:
        return Language.HI
    if tel > 2:
        return Language.TE
    words = _WORD.findall(text.lower())
    hi = sum(w in _HINGLISH for w in words)
    te = sum(w in _TENGLISH for w in words)
    if te >= 2 and te >= hi:
        return Language.TE
    if hi >= 2:
        return Language.HI
    return Language.EN


@dataclass(frozen=True)
class _Hit:
    pid: int
    category: Category
    strength: float
    excerpt: str
    start: int
    end: int


@dataclass
class ConversationAnalysis:
    """Aggregated conversation signals."""

    activations: dict[Category, float] = field(default_factory=dict)
    evidence: list[Evidence] = field(default_factory=list)
    languages: list[Language] = field(default_factory=list)
    advisory: float = 0.0

    def get(self, category: Category) -> float:
        """Returns the activation of ``category`` (0 if absent)."""
        return self.activations.get(category, 0.0)


@functools.lru_cache(maxsize=16384)
def _hits(text: str) -> tuple[tuple[_Hit, ...], float]:
    """Finds lexicon hits in one utterance; returns (hits, advisory_strength)."""
    norm = normalize(text)
    raw: list[_Hit] = []
    suppressed = 1.0
    for e in ENTRIES:
        m = e.pattern.search(norm)
        if m is None:
            continue
        if (e.category in NEGATION_SENSITIVE and is_negated(norm, m.start())) or (
            e.category is Category.SECRECY and is_credential_advisory(norm, m.start(), m.end())
        ):
            suppressed *= 1 - 0.8 * e.weight
            continue
        raw.append(_Hit(e.pid, e.category, e.weight, m.group(0)[:60], m.start(), m.end()))
    # Keep the strongest hit per overlapping span within a category.
    raw.sort(key=lambda h: -h.strength)
    kept: list[_Hit] = []
    for h in raw:
        if any(k.category == h.category and h.start < k.end and k.start < h.end for k in kept):
            continue
        kept.append(h)
    return tuple(kept), 1 - suppressed


class ScamSignalDetector:
    """Transparent, multilingual tactic detector."""

    def analyze(self, transcript: Sequence[Utterance]) -> ConversationAnalysis:
        """Analyses a transcript and returns per-tactic activations with evidence."""
        by_pid: dict[int, list[tuple[float, Evidence]]] = {}
        advisory_keep = 1.0
        lang_counts: dict[Language, int] = {}
        for idx, utt in enumerate(transcript):
            if utt.speaker is Speaker.CALLER:
                lang_counts[detect_language(utt.text)] = (
                    lang_counts.get(detect_language(utt.text), 0) + 1
                )
            hits, adv = _hits(utt.text)
            advisory_keep *= 1 - adv
            for h in hits:
                mult = (
                    _USER_MULT.get(h.category, _DEFAULT_USER_MULT)
                    if utt.speaker is Speaker.USER
                    else 1.0
                )
                strength = h.strength * mult
                if strength <= 0:
                    continue
                ev = Evidence(
                    category=h.category,
                    excerpt=h.excerpt,
                    utterance_index=idx,
                    t=utt.t,
                    strength=round(strength, 3),
                )
                by_pid.setdefault(h.pid, []).append((strength, ev))

        keep: dict[Category, float] = {}
        evidence: list[Evidence] = []
        for items in by_pid.values():
            best_strength, best_ev = max(items, key=lambda x: x[0])
            repeats = min(len(items) - 1, 4)
            eff = 1 - (1 - best_strength) ** (1 + 0.25 * repeats)
            cat = best_ev.category
            keep[cat] = keep.get(cat, 1.0) * (1 - eff)
            first = min(items, key=lambda x: x[1].utterance_index)[1]
            evidence.append(first.model_copy(update={"strength": round(best_strength, 3)}))
        activations = {c: min(0.99, 1 - k) for c, k in keep.items()}
        evidence.sort(key=lambda e: (-e.strength, e.t))
        langs = [lang for lang, _ in sorted(lang_counts.items(), key=lambda kv: -kv[1])]
        return ConversationAnalysis(
            activations=activations,
            evidence=evidence[:16],
            languages=langs,
            advisory=round(1 - advisory_keep, 3),
        )


def tactic_pressure(activations: dict[Category, float]) -> float:
    """Noisy-OR of coercive tactics; used by interaction features."""
    keep = 1.0
    for cat in (
        Category.AUTHORITY,
        Category.THREAT,
        Category.SECRECY,
        Category.SAFE_ACCOUNT,
        Category.CREDENTIAL,
        Category.REMOTE_ACCESS,
        Category.KYC_BLOCK,
        Category.PRIZE_REFUND,
        Category.INVESTMENT,
        Category.COURIER,
        Category.FAMILY,
    ):
        keep *= 1 - 0.8 * activations.get(cat, 0.0)
    return 1 - keep


def logistic(x: float) -> float:
    """Numerically stable logistic function."""
    if x >= 0:
        return 1 / (1 + math.exp(-x))
    z = math.exp(x)
    return z / (1 + z)
