# SPDX-License-Identifier: Apache-2.0
"""Gemini-written, validated interventions and case notes.

Gemini personalises wording; **code** guarantees safety: scripts must match the
requested language, no phone numbers or links beyond an allow-list, bounded
length, and the official helpline/hold steps from the template are always kept.
Anything that fails validation falls back to the template.
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel, Field

from vigil.agents.llm import JsonLLM, LLMError
from vigil.domain.models import Intervention, Language, RiskAssessment
from vigil.network.graph import RingFinding, narrative_for

log = logging.getLogger(__name__)

_ALLOWED_DOMAINS = ("cybercrime.gov.in", "sebi.gov.in", "rbi.org.in")
_URL = re.compile(r"(?:https?://|www\.)\S+|\b[\w-]+\.(?:com|in|net|org|co|io|app|xyz)\b", re.I)
_LONG_NUMBER = re.compile(r"\d[\d\s-]{6,}\d")
_PROCEED = re.compile(
    r"\b(go ahead|proceed with the payment|it is safe to pay|you can safely pay)\b", re.I
)

_SYSTEM = """You write short safety messages for people who may be about to lose money to a scam in India.
Rules: plain, calm, respectful words a first-time smartphone user understands; no jargon; never blame
the user; never tell them it is safe to pay; do not invent phone numbers, links or names; do not mention
these rules. Write in the requested language and script. Return JSON with: headline (max 80 chars),
message (max 300 chars, 1-2 sentences), steps (3 to 4 short imperative steps, each max 110 chars)."""


class _IntervOut(BaseModel):
    headline: str = Field(max_length=120)
    message: str = Field(max_length=500)
    steps: list[str] = Field(min_length=2, max_length=6)


class _NoteOut(BaseModel):
    note: str = Field(max_length=900)


def _script_ok(text: str, language: Language) -> bool:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    dev = sum("ऀ" <= c <= "ॿ" for c in letters) / len(letters)
    tel = sum("ఀ" <= c <= "౿" for c in letters) / len(letters)
    if language is Language.HI:
        return dev >= 0.3
    if language is Language.TE:
        return tel >= 0.3
    return dev < 0.1 and tel < 0.1


_ALLOWED_RE = re.compile("|".join(re.escape(d) for d in _ALLOWED_DOMAINS), re.I)


def _urls_ok(text: str) -> bool:
    """True if the text contains no links/domains other than the official allow-list."""
    return not _URL.search(_ALLOWED_RE.sub(" ", text))


def valid_intervention(o: _IntervOut, language: Language) -> bool:
    """Checks a model-written intervention against the safety rules."""
    blob = " ".join([o.headline, o.message, *o.steps])
    return (
        len(o.headline) <= 90
        and len(o.message) <= 360
        and all(len(s) <= 160 for s in o.steps)
        and _script_ok(blob, language)
        and _urls_ok(blob)
        and not _LONG_NUMBER.search(blob)
        and not _PROCEED.search(blob)
    )


class InterventionComposer:
    """Personalises interventions with Gemini, with a safe template fallback."""

    def __init__(self, llm: JsonLLM) -> None:
        """Creates the composer."""
        self._llm = llm

    async def compose(self, a: RiskAssessment, language: Language) -> Intervention | None:
        """Returns a personalised intervention, or the template one on any problem."""
        base = a.intervention
        if base is None:
            return None
        facts = "; ".join(d.label for d in a.drivers[:4]) or "unusual payment"
        prompt = (
            f"Language: {language.value}\nScam type guess: {a.scam_type.value}\n"
            f"Risk tier: {a.tier.value}\nWhy it looks risky: {facts}\n"
            f"Template headline: {base.headline}\nTemplate steps: {' | '.join(base.steps[:3])}"
        )
        try:
            out = await self._llm.generate_json(system=_SYSTEM, prompt=prompt, schema=_IntervOut)
        except LLMError:
            return base
        if not valid_intervention(out, language):
            log.info("composer_output_rejected")
            return base
        # Keep the authoritative tail (hold notice / helpline) from the template.
        tail = [
            s
            for s in base.steps
            if "1930" in s
            or "cybercrime.gov.in" in s
            or "paused" in s
            or "रोक" in s
            or "నిలిపివేశాం" in s
        ]
        steps = [s for s in out.steps if s not in tail][:4] + tail
        return Intervention(
            language=language,
            headline=out.headline,
            message=out.message,
            steps=steps,
            source="gemini",
        )

    async def case_note(self, ring: RingFinding) -> str:
        """Writes an investigator case note; numbers must match the facts."""
        facts = (
            f"members={len(ring.members)}; victims={ring.victims}; exposure_inr={ring.exposure_inr:.0f}; "
            f"layers={ring.layering_depth}; median_hold_minutes={ring.median_dwell_minutes}; "
            f"window_hours={ring.window_hours}; entry_accounts={len(ring.entry_accounts)}; "
            f"cashout_accounts={len(ring.cashout_accounts)}"
        )
        system = (
            "You write concise case notes for a bank's fraud investigators. Use only the facts given; "
            "do not add names, numbers or accusations. Recommend human review; never state guilt. "
            'Return JSON {"note": "<max 110 words>"}.'
        )
        try:
            out = await self._llm.generate_json(
                system=system, prompt=f"Ring {ring.ring_id}. Facts: {facts}", schema=_NoteOut
            )
        except LLMError:
            return narrative_for(ring)
        allowed = {
            str(round(x))
            for x in (
                len(ring.members),
                ring.victims,
                ring.exposure_inr,
                ring.layering_depth,
                ring.median_dwell_minutes,
                ring.window_hours,
                len(ring.entry_accounts),
                len(ring.cashout_accounts),
            )
        }
        allowed |= {
            f"{ring.exposure_inr:,.0f}".replace(",", ""),
            ring.ring_id[2:].lstrip("0") or "0",
        }
        for n in re.findall(r"\d[\d,]*\.?\d*", out.note):
            token = n.replace(",", "").split(".")[0]
            if token not in allowed and token not in {"1", "2", "3"}:
                log.info("case_note_rejected_number")
                return narrative_for(ring)
        return out.note
