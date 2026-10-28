# SPDX-License-Identifier: Apache-2.0
"""Local PII redaction applied before any text leaves the trust boundary.

This is a deterministic first line of defence. In production, pair it with
Google Cloud Sensitive Data Protection (DLP) via the ``Redactor`` protocol; the
local redactor keeps the system safe and testable when DLP is unavailable.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass, field
from typing import Protocol

# Devanagari and Telugu digits -> ASCII, so numeric patterns match all scripts.
_DIGIT_MAP = {
    **{ord("०") + i: ord("0") + i for i in range(10)},
    **{ord("౦") + i: ord("0") + i for i in range(10)},
}

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_VPA = re.compile(r"\b[\w.\-]{2,64}@[A-Za-z][A-Za-z0-9]{1,30}\b")
_PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
_IFSC = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
_OTP = re.compile(
    r"(?i)(\b(?:otp|pin|cvv|password|passcode)\b|ओटीपी|पिन|ఓటీపీ|పిన్)"
    r"([^\d\n]{0,30})(\d{4,8})"
)
_AADHAAR = re.compile(r"(?<!\d)[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}(?!\d)")
_PHONE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
_ACCOUNT = re.compile(r"(?<!\d)\d{9,18}(?!\d)")


def _luhn_ok(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d *= 2
            d -= 9 if d > 9 else 0
        total += d
        alt = not alt
    return total % 10 == 0


@dataclass
class RedactionResult:
    """Redacted text plus a count of what was removed (never the values)."""

    text: str
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        """Total number of redactions."""
        return sum(self.counts.values())


class Redactor(Protocol):
    """Interface satisfied by the local redactor and a DLP-backed one."""

    def redact(self, text: str) -> RedactionResult:
        """Returns ``text`` with sensitive values replaced by placeholders."""
        ...


class LocalRedactor:
    """Regex-based redactor for Indian financial identifiers."""

    def redact(self, text: str) -> RedactionResult:
        """Redacts emails, UPI IDs, PAN, IFSC, OTP/PIN, Aadhaar, phone, card, account."""
        counts: dict[str, int] = {}
        out = text.translate(_DIGIT_MAP)

        def sub(pattern: re.Pattern[str], label: str, s: str) -> str:
            def repl(_: re.Match[str]) -> str:
                counts[label] = counts.get(label, 0) + 1
                return f"[{label}]"

            return pattern.sub(repl, s)

        out = sub(_EMAIL, "EMAIL", out)
        out = sub(_VPA, "UPI_ID", out)
        out = sub(_PAN, "PAN", out)
        out = sub(_IFSC, "IFSC", out)

        def otp_repl(m: re.Match[str]) -> str:
            counts["OTP"] = counts.get("OTP", 0) + 1
            return f"{m.group(1)}{m.group(2)}[OTP]"

        out = _OTP.sub(otp_repl, out)
        out = sub(_AADHAAR, "AADHAAR", out)
        out = sub(_PHONE, "PHONE", out)

        def card_repl(m: re.Match[str]) -> str:
            digits = re.sub(r"\D", "", m.group(0))
            if 13 <= len(digits) <= 19 and _luhn_ok(digits):
                counts["CARD"] = counts.get("CARD", 0) + 1
                return "[CARD]"
            return m.group(0)

        out = _CARD.sub(card_repl, out)
        out = sub(_ACCOUNT, "ACCOUNT", out)
        return RedactionResult(out, counts)


_PROCESS_SALT = hashlib.sha256(b"vigil-log-pseudonym").digest()


def pseudonym(value: str, key: bytes = _PROCESS_SALT) -> str:
    """Returns a short stable pseudonym for logs (HMAC-SHA256, 12 hex chars)."""
    return hmac.new(key, value.encode(), hashlib.sha256).hexdigest()[:12]
