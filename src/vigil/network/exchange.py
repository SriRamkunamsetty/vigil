# SPDX-License-Identifier: Apache-2.0
"""Privacy-preserving cross-institution signal exchange.

Institutions publish *keyed hashes* (HMAC-SHA256) of confirmed mule accounts and
scam payees, never raw identifiers or customer data. A signal only reaches full
strength once ``min_reporters`` distinct institutions corroborate it, which
limits harm from a single mistaken or malicious report. Signals expire and can
be retracted.

Limits (documented in ``docs/THREAT_MODEL.md``): keyed hashing hides identifiers
from outsiders but a member holding the key can test guesses for low-entropy
identifiers. The roadmap replaces lookups with private set intersection.
"""

from __future__ import annotations

import hashlib
import hmac
import math
import re
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

_KINDS = {"payee", "account", "phone", "device"}


def normalize_identifier(kind: str, identifier: str) -> str:
    """Canonicalises an identifier before hashing."""
    s = identifier.strip().lower()
    if kind == "phone":
        digits = re.sub(r"\D", "", s)
        return digits[-10:]
    if kind == "account":
        return re.sub(r"\D", "", s)
    return s


class SignalLookup(BaseModel):
    """Result of a lookup."""

    flag: float = Field(ge=0, le=1, description="0 none, 0.6 single report, 1.0 corroborated")
    reporters: int = 0
    corroborated: bool = False


@dataclass
class _Entry:
    reports: dict[str, tuple[float, float]] = field(default_factory=dict)  # reporter -> (ts, conf)


class RateLimited(Exception):
    """Raised when an institution publishes too fast."""


class BloomFilter:
    """Compact set membership with no false negatives."""

    def __init__(self, n_items: int, fp_rate: float = 0.01) -> None:
        """Sizes the filter for ``n_items`` at ``fp_rate``."""
        n = max(1, n_items)
        self.m = max(64, int(-n * math.log(fp_rate) / (math.log(2) ** 2)))
        self.k = max(1, round(self.m / n * math.log(2)))
        self.bits = bytearray((self.m + 7) // 8)

    def _positions(self, token: str) -> list[int]:
        h = hashlib.sha256(token.encode()).digest()
        a = int.from_bytes(h[:8], "big")
        b = int.from_bytes(h[8:16], "big") | 1
        return [(a + i * b) % self.m for i in range(self.k)]

    def add(self, token: str) -> None:
        """Adds a token."""
        for p in self._positions(token):
            self.bits[p // 8] |= 1 << (p % 8)

    def __contains__(self, token: str) -> bool:
        return all(self.bits[p // 8] & (1 << (p % 8)) for p in self._positions(token))


class SignalExchange:
    """In-memory consortium signal store (swap for Firestore/Spanner in production)."""

    def __init__(
        self,
        key: bytes,
        min_reporters: int = 2,
        ttl_days: int = 30,
        max_publishes_per_hour: int = 500,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """Creates an exchange.

        Args:
            key: Consortium HMAC key.
            min_reporters: Distinct institutions needed to corroborate.
            ttl_days: Signal lifetime.
            max_publishes_per_hour: Per-institution rate limit (anti-poisoning).
            clock: Injectable clock for tests.
        """
        self._key = key
        self._min = min_reporters
        self._ttl = ttl_days * 86400
        self._rate = max_publishes_per_hour
        self._clock = clock
        self._entries: dict[str, _Entry] = defaultdict(_Entry)
        self._recent: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def token(self, kind: str, identifier: str) -> str:
        """Returns the keyed hash for an identifier."""
        if kind not in _KINDS:
            raise ValueError(f"unknown kind {kind!r}")
        msg = f"{kind}|{normalize_identifier(kind, identifier)}".encode()
        return hmac.new(self._key, msg, hashlib.sha256).hexdigest()

    def publish(self, reporter: str, kind: str, identifier: str, confidence: float = 0.9) -> str:
        """Publishes a signal from ``reporter``; returns the opaque token."""
        tok = self.token(kind, identifier)
        now = self._clock()
        with self._lock:
            q = self._recent[reporter]
            while q and now - q[0] > 3600:
                q.popleft()
            if len(q) >= self._rate:
                raise RateLimited(reporter)
            q.append(now)
            self._entries[tok].reports[reporter] = (now, confidence)
        return tok

    def retract(self, reporter: str, kind: str, identifier: str) -> bool:
        """Withdraws a prior report (e.g. after a successful appeal)."""
        tok = self.token(kind, identifier)
        with self._lock:
            return self._entries[tok].reports.pop(reporter, None) is not None

    def lookup(self, kind: str, identifier: str) -> SignalLookup:
        """Looks up an identifier."""
        tok = self.token(kind, identifier)
        now = self._clock()
        with self._lock:
            live = [r for r, (ts, _) in self._entries[tok].reports.items() if now - ts <= self._ttl]
        n = len(live)
        if n == 0:
            return SignalLookup(flag=0.0)
        corroborated = n >= self._min
        return SignalLookup(
            flag=1.0 if corroborated else 0.6, reporters=n, corroborated=corroborated
        )

    def payee_check(self) -> Callable[[str], float]:
        """Returns a callable usable as the risk engine's ``PayeeCheck``."""
        return lambda payee: self.lookup("payee", payee).flag

    def export_bloom(self, fp_rate: float = 0.01) -> BloomFilter:
        """Exports corroborated tokens as a Bloom filter for institution-side caches."""
        now = self._clock()
        with self._lock:
            toks = [
                t
                for t, e in self._entries.items()
                if sum(1 for ts, _ in e.reports.values() if now - ts <= self._ttl) >= self._min
            ]
        bf = BloomFilter(len(toks), fp_rate)
        for t in toks:
            bf.add(t)
        return bf

    def stats(self) -> dict[str, int]:
        """Aggregate counts (no identifiers)."""
        now = self._clock()
        with self._lock:
            live = {
                t: sum(1 for ts, _ in e.reports.values() if now - ts <= self._ttl)
                for t, e in self._entries.items()
            }
        return {
            "signals": sum(1 for n in live.values() if n > 0),
            "corroborated": sum(1 for n in live.values() if n >= self._min),
        }
