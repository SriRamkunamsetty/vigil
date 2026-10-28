# SPDX-License-Identifier: Apache-2.0
"""Typed request/response models shared by the engine, agents and API."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Language(StrEnum):
    """Supported interface languages."""

    EN = "en"
    HI = "hi"
    TE = "te"


class Speaker(StrEnum):
    """Who produced an utterance."""

    CALLER = "caller"
    USER = "user"
    SYSTEM = "system"


class Tier(StrEnum):
    """Friction tier, ordered by severity."""

    ALLOW = "allow"
    NUDGE = "nudge"
    FRICTION = "friction"
    HOLD = "hold"

    @property
    def rank(self) -> int:
        """Numeric severity for comparisons."""
        return list(Tier).index(self)


class ScamType(StrEnum):
    """Scam typologies Vigil can name."""

    DIGITAL_ARREST = "digital_arrest"
    KYC_OTP = "kyc_otp_fraud"
    INVESTMENT = "investment_fraud"
    COURIER_CUSTOMS = "courier_customs"
    PRIZE_REFUND = "prize_refund"
    FAMILY_EMERGENCY = "family_emergency"
    REMOTE_ACCESS = "remote_access_support"
    NONE = "none"


class Category(StrEnum):
    """Social-engineering tactics detected in conversation."""

    AUTHORITY = "authority_impersonation"
    BANK_CLAIM = "bank_official_claim"
    THREAT = "threat_of_arrest_or_loss"
    SECRECY = "secrecy_isolation"
    URGENCY = "urgency"
    CREDENTIAL = "credential_request"
    REMOTE_ACCESS = "remote_access_request"
    KYC_BLOCK = "kyc_or_account_block"
    SAFE_ACCOUNT = "safe_account_transfer"
    PRIZE_REFUND = "prize_or_refund_bait"
    INVESTMENT = "guaranteed_returns"
    COURIER = "courier_parcel_pretext"
    FAMILY = "family_emergency_pretext"
    PAYMENT = "payment_instruction"
    INJECTION = "ai_manipulation_attempt"


class Utterance(BaseModel):
    """One turn of a call or chat."""

    model_config = ConfigDict(frozen=True)

    speaker: Speaker
    text: str = Field(max_length=2000)
    t: float = Field(ge=0, description="Seconds since the conversation began.")


class UserProfile(BaseModel):
    """Opaque, minimal user context. No names, numbers or account IDs."""

    user_id: str = Field(max_length=128, description="Opaque pseudonymous ID.")
    preferred_language: Language = Language.EN
    senior: bool = Field(False, description="Opted-in extra protection (e.g. 60+).")
    trusted_contact_opted_in: bool = False
    max_txn_30d_inr: float = Field(5000.0, ge=0)
    avg_txn_inr: float = Field(1500.0, ge=0)


class TransactionContext(BaseModel):
    """Context for a payment the user is about to make."""

    amount_inr: float = Field(gt=0, le=1e9)
    payee_ref: str = Field(max_length=256, description="Payee VPA/account (never logged).")
    payee_first_time: bool = False
    payee_account_age_days: int | None = Field(None, ge=0)
    payee_is_merchant: bool = False
    hour_of_day: int = Field(12, ge=0, le=23)
    device_new: bool = False
    sim_swap_recent: bool = False
    active_call_with_unknown_number: bool = False
    call_duration_s: float = Field(0.0, ge=0)
    screen_sharing_active: bool = False
    txn_count_last_hour: int = Field(0, ge=0)


class AssessRequest(BaseModel):
    """Input to ``/v1/assess``."""

    profile: UserProfile
    transcript: list[Utterance] = Field(default_factory=list, max_length=200)
    txn: TransactionContext | None = None


class Evidence(BaseModel):
    """A span of conversation that triggered a tactic."""

    category: Category
    excerpt: str
    utterance_index: int
    t: float
    strength: float = Field(ge=0, le=1)


class Driver(BaseModel):
    """One term of the additive (log-odds) explanation."""

    feature: str
    label: str
    value: float = Field(description="Feature activation in [0, 1].")
    contribution: float = Field(description="Log-odds contribution.")


class Intervention(BaseModel):
    """Plain-language guidance shown to the user."""

    language: Language
    headline: str
    message: str
    steps: list[str]
    source: str = Field("template", description="template | gemini")


class Actions(BaseModel):
    """Machine-readable actions the client/bank should take."""

    delay_seconds: int = 0
    hold_for_review: bool = False
    require_verified_callback: bool = False
    offer_trusted_contact_alert: bool = False
    show_helpline_1930: bool = False


class RiskAssessment(BaseModel):
    """Full, explainable risk decision."""

    score: float = Field(ge=0, le=1)
    tier: Tier
    phase: str = Field(description="call | payment")
    scam_type: ScamType
    scam_type_confidence: float = Field(ge=0, le=1)
    drivers: list[Driver]
    protective: list[Driver]
    evidence: list[Evidence]
    languages_detected: list[Language]
    intervention: Intervention | None
    actions: Actions
    first_flag_t: float | None = Field(
        None, description="Conversation time at which risk first reached NUDGE."
    )
    model_version: str
    latency_ms: float = 0.0
    ai_layer: str = Field(
        "off",
        description="Gemini semantic layer: off | used | unavailable. "
        "The tier never depends on it being available.",
    )
