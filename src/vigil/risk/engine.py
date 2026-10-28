# SPDX-License-Identifier: Apache-2.0
"""The deterministic risk engine: transcript + payment context -> decision.

The LLM is *not* in this path. Gemini explains and converses around the
decision, but the tier is always produced here, so it is fast, testable,
auditable and immune to prompt injection by a scammer on the call.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence

from vigil import MODEL_VERSION
from vigil.domain.models import (
    AssessRequest,
    Category,
    Evidence,
    Language,
    RiskAssessment,
    Tier,
    Utterance,
)
from vigil.risk import friction, interventions, model
from vigil.risk.behaviour import behaviour_features
from vigil.risk.scam_signals import ConversationAnalysis, ScamSignalDetector
from vigil.risk.scam_type import classify

PayeeCheck = Callable[[str], float]
"""Returns the cross-bank flag for a payee: 0 none, 0.6 single report, 1.0 corroborated."""


def _no_signal(_: str) -> float:
    return 0.0


class RiskEngine:
    """Scores a conversation and/or payment and chooses proportionate friction."""

    def __init__(
        self,
        detector: ScamSignalDetector | None = None,
        payee_check: PayeeCheck | None = None,
    ) -> None:
        """Creates an engine.

        Args:
            detector: Conversation tactic detector (default: lexicon-based).
            payee_check: Cross-bank signal lookup for payees.
        """
        self._detector = detector or ScamSignalDetector()
        self._payee_check = payee_check or _no_signal

    def assess(
        self,
        req: AssessRequest,
        extra_activations: dict[Category, float] | None = None,
        extra_evidence: Sequence[Evidence] = (),
    ) -> RiskAssessment:
        """Produces a full explainable assessment.

        Args:
            req: Conversation and payment context.
            extra_activations: Optional tactic activations from the Gemini
                semantic layer. They are merged with ``max`` so the LLM can only
                *raise* a tactic's activation, never lower it; a scammer who
                tries to talk the reviewer into a "safe" verdict gains nothing.
            extra_evidence: Evidence spans that accompany those activations.
        """
        start = time.perf_counter()
        analysis = self._detector.analyze(req.transcript)
        if extra_activations:
            for cat, v in extra_activations.items():
                analysis.activations[cat] = max(
                    analysis.activations.get(cat, 0.0), min(max(v, 0.0), 0.95)
                )
            analysis.evidence = sorted(
                [*analysis.evidence, *extra_evidence], key=lambda e: (-e.strength, e.t)
            )[:16]
        behaviour = None
        if req.txn is not None:
            flag = self._payee_check(req.txn.payee_ref)
            behaviour = behaviour_features(req.profile, req.txn, flag)

        lang = req.profile.preferred_language
        out = model.score(model.build_features(analysis, behaviour), lang)
        thr = friction.thresholds_for(req.txn, req.profile)
        tier = friction.decide(out.probability, req.txn is not None, thr)
        scam_type, conf = classify(analysis.activations)
        actions = friction.actions_for(tier, req.txn, req.profile, scam_type, out.probability)
        phase = "payment" if req.txn is not None else "call"
        return RiskAssessment(
            score=round(out.probability, 4),
            tier=tier,
            phase=phase,
            scam_type=scam_type,
            scam_type_confidence=conf,
            drivers=out.drivers[:8],
            protective=out.protective[:4],
            evidence=analysis.evidence,
            languages_detected=analysis.languages or [Language.EN],
            intervention=interventions.template(lang, scam_type, tier, conf, phase),
            actions=actions,
            first_flag_t=self.first_flag_time(req.transcript, req.profile.senior),
            model_version=MODEL_VERSION,
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
        )

    def conversation_score(self, transcript: Sequence[Utterance]) -> float:
        """Risk probability from the conversation alone."""
        analysis: ConversationAnalysis = self._detector.analyze(transcript)
        return model.score(model.build_features(analysis, None)).probability

    def first_flag_time(
        self, transcript: Sequence[Utterance], senior: bool = False
    ) -> float | None:
        """Conversation time at which risk first reached the NUDGE threshold."""
        nudge = max(0.15, friction.Thresholds().nudge - (0.025 if senior else 0.0))
        for i in range(1, len(transcript) + 1):
            if self.conversation_score(transcript[:i]) >= nudge:
                return transcript[i - 1].t
        return None


__all__ = ["PayeeCheck", "RiskEngine", "Tier"]
