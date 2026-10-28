# SPDX-License-Identifier: Apache-2.0
"""Hand-written demo calls for the UI. All text is fictional."""

from __future__ import annotations

from typing import Any

from vigil.domain.models import Language

# Each turn: (speaker, text, seconds). `txn` is shown at the payment moment.
DEMO_CALLS: list[dict[str, Any]] = [
    {
        "id": "digital_arrest_en",
        "title": "“Digital arrest” call",
        "language": Language.EN,
        "senior": True,
        "blurb": "A caller says they are police and that you are under arrest unless you pay.",
        "turns": [
            (
                "caller",
                "Hello, this is Inspector Rao from the CBI cyber cell. A parcel in your name was found with illegal items.",
                0,
            ),
            ("user", "What? I did not send any parcel.", 8),
            (
                "caller",
                "You are now under digital arrest. Do not disconnect this call and do not tell anyone, not even your family.",
                16,
            ),
            ("user", "I am scared. What should I do?", 24),
            (
                "caller",
                "To clear your name you must move your savings to the RBI safe account immediately. Otherwise we will arrest you today.",
                32,
            ),
            ("user", "Okay... I will send it now.", 40),
        ],
        "txn": {
            "amount_inr": 150000,
            "payee_ref": "rbi.safe99@okbank",
            "payee_first_time": True,
            "payee_account_age_days": 6,
            "active_call_with_unknown_number": True,
            "call_duration_s": 2400,
            "hour_of_day": 15,
        },
    },
    {
        "id": "kyc_hi",
        "title": "बैंक KYC कॉल (हिन्दी)",
        "language": Language.HI,
        "senior": False,
        "blurb": "Caller asks for an OTP to “update KYC”, in Hinglish.",
        "turns": [
            (
                "caller",
                "Sir main SBI bank se bol raha hoon. Aapka KYC expire ho gaya hai, aaj hi account block ho jayega.",
                0,
            ),
            ("user", "Achha, ab kya karna hai?", 9),
            (
                "caller",
                "Aapke phone par ek OTP aaya hoga, wo mujhe abhi bataiye. Jaldi kijiye, warna account band ho jayega.",
                18,
            ),
            ("user", "Haan, ek minute.", 26),
        ],
        "txn": None,
    },
    {
        "id": "investment_te",
        "title": "పెట్టుబడి మోసం (తెలుగు)",
        "language": Language.TE,
        "senior": False,
        "blurb": "A “trading tips” group promises guaranteed returns.",
        "turns": [
            (
                "caller",
                "హాయ్ సార్, మా VIP ట్రేడింగ్ గ్రూప్‌లో చేరండి. రోజుకు 5% గ్యారంటీ రిటర్న్స్ ఇస్తాం, నష్టం అసలు ఉండదు.",
                0,
            ),
            ("user", "నిజమా? ఎంత పెట్టాలి?", 10),
            ("caller", "ఈ రోజే 50,000 పెట్టండి. ఇది ఎవరికీ చెప్పకండి, ఆఫర్ ఈ రోజు మాత్రమే.", 20),
        ],
        "txn": {
            "amount_inr": 50000,
            "payee_ref": "vip.trade@upi",
            "payee_first_time": True,
            "payee_account_age_days": 12,
            "hour_of_day": 21,
        },
    },
    {
        "id": "genuine_bank",
        "title": "Genuine bank reminder (should stay quiet)",
        "language": Language.EN,
        "senior": False,
        "blurb": "A real alert that mentions OTP safety. Vigil should not cry wolf.",
        "turns": [
            (
                "caller",
                "Hello, this is an automated message from your bank. Your card ending 1234 was used at a grocery store.",
                0,
            ),
            (
                "caller",
                "If this was you, no action is needed. Never share your OTP or PIN with anyone, including bank staff.",
                9,
            ),
            ("user", "Yes, that was me. Thanks.", 17),
        ],
        "txn": {
            "amount_inr": 1200,
            "payee_ref": "freshmart@upi",
            "payee_is_merchant": True,
            "hour_of_day": 18,
        },
    },
]
