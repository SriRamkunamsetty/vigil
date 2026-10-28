# SPDX-License-Identifier: Apache-2.0
"""Explainable log-odds risk model.

The model is a generalised additive model in log-odds space: every feature
contributes ``weight * activation`` and the contributions are shown to the user
and to auditors. There are no hidden interactions; the few interaction terms are
named features.

Weights are *priors* set from published scam typologies and reviewed against a
development split of synthetic data (see ``docs/EVALUATION.md``). They are not
fitted to real fraud data, which this project does not have. Production use
requires re-fitting on the institution's labelled data with
:func:`vigil.risk.calibration.fit_logistic` and a prevalence correction.
"""

from __future__ import annotations

from dataclasses import dataclass

from vigil.domain.models import Category as C
from vigil.domain.models import Driver, Language
from vigil.risk.scam_signals import ConversationAnalysis, logistic, tactic_pressure

BIAS = -4.6

# feature -> weight (log-odds at activation 1.0)
WEIGHTS: dict[str, float] = {
    # conversation tactics
    C.AUTHORITY.value: 1.5,
    C.BANK_CLAIM.value: 0.7,
    C.THREAT.value: 2.1,
    C.SECRECY.value: 2.0,
    C.URGENCY.value: 0.9,
    C.CREDENTIAL.value: 2.3,
    C.REMOTE_ACCESS.value: 2.4,
    C.KYC_BLOCK.value: 1.6,
    C.SAFE_ACCOUNT.value: 3.0,
    C.PRIZE_REFUND.value: 2.6,
    C.INVESTMENT.value: 3.0,
    C.COURIER.value: 1.3,
    C.FAMILY.value: 2.2,
    C.PAYMENT.value: 0.8,
    C.INJECTION.value: 2.0,
    "advisory_language": -1.0,
    # behaviour
    "amount_ratio": 0.8,
    "large_absolute": 0.5,
    "new_payee": 0.9,
    "young_payee_account": 0.7,
    "network_flag": 3.2,
    "active_call": 1.0,
    "long_call": 0.6,
    "screen_sharing": 2.2,
    "new_device": 0.8,
    "sim_swap": 1.2,
    "night": 0.4,
    "velocity": 0.7,
    "merchant": -1.0,
    # named interactions
    "authority_x_threat": 1.2,
    "secrecy_x_pressure": 1.0,
    "pressured_new_payee": 1.5,
    "coached_payment_on_call": 1.6,
    "credential_x_pretext": 1.2,
}

LABELS: dict[Language, dict[str, str]] = {
    Language.EN: {
        C.AUTHORITY.value: "Caller claims to be police / a government agency",
        C.BANK_CLAIM.value: "Caller claims to be from your bank",
        C.THREAT.value: "Threat of arrest or legal action",
        C.SECRECY.value: "Told to keep it secret / stay on the call",
        C.URGENCY.value: "Pressure to act immediately",
        C.CREDENTIAL.value: "Asked for OTP / PIN / password",
        C.REMOTE_ACCESS.value: "Asked to install an app or share screen",
        C.KYC_BLOCK.value: "KYC / account-block scare",
        C.SAFE_ACCOUNT.value: "Asked to move money to a 'safe' or 'verification' account",
        C.PRIZE_REFUND.value: "Prize, refund or fee bait",
        C.INVESTMENT.value: "Guaranteed-returns promise",
        C.COURIER.value: "Parcel / customs / Aadhaar-misuse story",
        C.FAMILY.value: "Family-emergency story",
        C.PAYMENT.value: "Caller is telling you to send money",
        C.INJECTION.value: "Attempt to manipulate this AI reviewer",
        "advisory_language": "Genuine fraud-warning language present",
        "amount_ratio": "Amount is far above your usual payments",
        "large_absolute": "Large amount",
        "new_payee": "First payment to this person",
        "young_payee_account": "Receiver's account is very new",
        "network_flag": "Receiver reported by other banks",
        "active_call": "You are on a call with an unknown number",
        "long_call": "Long call in progress",
        "screen_sharing": "Screen sharing / remote control active",
        "new_device": "Payment from a new device",
        "sim_swap": "SIM recently changed",
        "night": "Unusual hour",
        "velocity": "Several payments in the last hour",
        "merchant": "Receiver is a registered merchant",
        "authority_x_threat": "Authority figure making threats",
        "secrecy_x_pressure": "Secrecy combined with pressure",
        "pressured_new_payee": "New receiver while being pressured",
        "coached_payment_on_call": "Paying while someone coaches you on a call",
        "credential_x_pretext": "Asked for OTP/PIN by someone posing as an official",
    },
    Language.HI: {
        C.AUTHORITY.value: "कॉल करने वाला खुद को पुलिस/सरकारी एजेंसी बता रहा है",
        C.BANK_CLAIM.value: "कॉल करने वाला खुद को आपका बैंक बता रहा है",
        C.THREAT.value: "गिरफ्तारी या कानूनी कार्रवाई की धमकी",
        C.SECRECY.value: "किसी को न बताने / कॉल न काटने को कहा गया",
        C.URGENCY.value: "तुरंत कदम उठाने का दबाव",
        C.CREDENTIAL.value: "OTP / PIN / पासवर्ड मांगा गया",
        C.REMOTE_ACCESS.value: "ऐप इंस्टॉल करने या स्क्रीन शेयर करने को कहा गया",
        C.KYC_BLOCK.value: "KYC / खाता बंद होने का डर",
        C.SAFE_ACCOUNT.value: "'सुरक्षित' या 'वेरिफिकेशन' खाते में पैसे भेजने को कहा गया",
        C.PRIZE_REFUND.value: "इनाम, रिफंड या फीस का लालच",
        C.INVESTMENT.value: "पक्के मुनाफे का वादा",
        C.COURIER.value: "पार्सल / कस्टम / आधार के दुरुपयोग की कहानी",
        C.FAMILY.value: "परिवार में आपात स्थिति की कहानी",
        C.PAYMENT.value: "कॉल करने वाला पैसे भेजने को कह रहा है",
        C.INJECTION.value: "इस AI समीक्षक को बहकाने की कोशिश",
        "advisory_language": "ठगी से बचाव की असली चेतावनी मौजूद है",
        "amount_ratio": "रकम आपके सामान्य भुगतान से बहुत ज़्यादा है",
        "large_absolute": "बड़ी रकम",
        "new_payee": "इस व्यक्ति को पहली बार भुगतान",
        "young_payee_account": "पाने वाले का खाता बिल्कुल नया है",
        "network_flag": "पाने वाले की दूसरे बैंकों ने शिकायत की है",
        "active_call": "आप किसी अनजान नंबर से कॉल पर हैं",
        "long_call": "लंबी कॉल चल रही है",
        "screen_sharing": "स्क्रीन शेयर / रिमोट कंट्रोल चालू है",
        "new_device": "नए डिवाइस से भुगतान",
        "sim_swap": "सिम हाल ही में बदला गया",
        "night": "असामान्य समय",
        "velocity": "पिछले एक घंटे में कई भुगतान",
        "merchant": "पाने वाला पंजीकृत दुकानदार है",
        "authority_x_threat": "अधिकारी बनकर धमकी दी जा रही है",
        "secrecy_x_pressure": "गोपनीयता के साथ दबाव",
        "pressured_new_payee": "दबाव में नए व्यक्ति को भुगतान",
        "coached_payment_on_call": "कॉल पर किसी के निर्देश पर भुगतान",
        "credential_x_pretext": "अधिकारी बनकर OTP/PIN माँगा गया",
    },
    Language.TE: {
        C.AUTHORITY.value: "కాల్ చేసిన వ్యక్తి పోలీసు/ప్రభుత్వ సంస్థ అని చెబుతున్నాడు",
        C.BANK_CLAIM.value: "కాల్ చేసిన వ్యక్తి మీ బ్యాంక్ అని చెబుతున్నాడు",
        C.THREAT.value: "అరెస్ట్ లేదా చట్టపరమైన చర్య బెదిరింపు",
        C.SECRECY.value: "ఎవరికీ చెప్పొద్దని / కాల్ కట్ చేయొద్దని చెప్పారు",
        C.URGENCY.value: "వెంటనే చర్య తీసుకోవాలనే ఒత్తిడి",
        C.CREDENTIAL.value: "OTP / PIN / పాస్‌వర్డ్ అడిగారు",
        C.REMOTE_ACCESS.value: "యాప్ ఇన్‌స్టాల్ చేయమని లేదా స్క్రీన్ షేర్ చేయమని అడిగారు",
        C.KYC_BLOCK.value: "KYC / ఖాతా బ్లాక్ భయం",
        C.SAFE_ACCOUNT.value: "'సేఫ్' లేదా 'వెరిఫికేషన్' ఖాతాకు డబ్బు పంపమని అడిగారు",
        C.PRIZE_REFUND.value: "బహుమతి, రీఫండ్ లేదా ఫీజు ఎర",
        C.INVESTMENT.value: "గ్యారెంటీ లాభం హామీ",
        C.COURIER.value: "పార్సిల్ / కస్టమ్స్ / ఆధార్ దుర్వినియోగం కథ",
        C.FAMILY.value: "కుటుంబ అత్యవసర పరిస్థితి కథ",
        C.PAYMENT.value: "కాల్ చేసిన వ్యక్తి డబ్బు పంపమని చెబుతున్నాడు",
        C.INJECTION.value: "ఈ AI సమీక్షకుడిని తప్పుదారి పట్టించే ప్రయత్నం",
        "advisory_language": "మోసాల గురించి నిజమైన హెచ్చరిక ఉంది",
        "amount_ratio": "మొత్తం మీ సాధారణ చెల్లింపుల కంటే చాలా ఎక్కువ",
        "large_absolute": "పెద్ద మొత్తం",
        "new_payee": "ఈ వ్యక్తికి మొదటిసారి చెల్లింపు",
        "young_payee_account": "అందుకునే వారి ఖాతా చాలా కొత్తది",
        "network_flag": "అందుకునే వారిపై ఇతర బ్యాంకులు ఫిర్యాదు చేశాయి",
        "active_call": "మీరు తెలియని నంబర్‌తో కాల్‌లో ఉన్నారు",
        "long_call": "ఎక్కువ సేపు కాల్ కొనసాగుతోంది",
        "screen_sharing": "స్క్రీన్ షేరింగ్ / రిమోట్ కంట్రోల్ ఆన్‌లో ఉంది",
        "new_device": "కొత్త డివైస్ నుంచి చెల్లింపు",
        "sim_swap": "సిమ్ ఇటీవల మార్చారు",
        "night": "అసాధారణ సమయం",
        "velocity": "గత గంటలో అనేక చెల్లింపులు",
        "merchant": "అందుకునే వారు నమోదిత వ్యాపారి",
        "authority_x_threat": "అధికారి పేరుతో బెదిరింపులు",
        "secrecy_x_pressure": "గోప్యతతో పాటు ఒత్తిడి",
        "pressured_new_payee": "ఒత్తిడిలో కొత్త వ్యక్తికి చెల్లింపు",
        "coached_payment_on_call": "కాల్‌లో ఎవరో చెప్పినట్లు చెల్లింపు",
        "credential_x_pretext": "అధికారిగా నటిస్తూ OTP/PIN అడిగారు",
    },
}


@dataclass
class ModelOutput:
    """Result of scoring one situation."""

    probability: float
    logit: float
    drivers: list[Driver]
    protective: list[Driver]
    features: dict[str, float]


def build_features(
    analysis: ConversationAnalysis, behaviour: dict[str, float] | None
) -> dict[str, float]:
    """Combines conversation and behaviour activations plus named interactions."""
    f: dict[str, float] = {c.value: analysis.get(c) for c in C}
    f["advisory_language"] = analysis.advisory
    has_txn = behaviour is not None
    if behaviour:
        f.update(behaviour)
    pressure = tactic_pressure(analysis.activations)
    f["authority_x_threat"] = f[C.AUTHORITY.value] * f[C.THREAT.value]
    f["secrecy_x_pressure"] = f[C.SECRECY.value] * max(
        f[C.THREAT.value], f[C.URGENCY.value], f[C.AUTHORITY.value]
    )
    # Asking for an OTP/PIN while posing as the bank, KYC desk, police or a prize
    # desk is the signature of credential fraud; legitimate parties never do both.
    f["credential_x_pretext"] = f[C.CREDENTIAL.value] * max(
        f[C.KYC_BLOCK.value], f[C.BANK_CLAIM.value], f[C.AUTHORITY.value], f[C.PRIZE_REFUND.value]
    )
    if has_txn:
        coercion = max(
            f[C.SECRECY.value],
            f[C.THREAT.value],
            f[C.URGENCY.value],
            f[C.AUTHORITY.value],
            f[C.SAFE_ACCOUNT.value],
            f[C.CREDENTIAL.value],
        )
        f["pressured_new_payee"] = f["new_payee"] * coercion
        f["coached_payment_on_call"] = f["active_call"] * pressure
    return f


def score(features: dict[str, float], language: Language = Language.EN) -> ModelOutput:
    """Scores ``features`` and returns the additive explanation."""
    labels = LABELS[language]
    logit = BIAS
    drivers: list[Driver] = []
    protective: list[Driver] = []
    for name, value in features.items():
        w = WEIGHTS.get(name)
        if w is None or value <= 0:
            continue
        contribution = w * value
        logit += contribution
        d = Driver(
            feature=name,
            label=labels.get(name, name),
            value=round(value, 3),
            contribution=round(contribution, 3),
        )
        (drivers if contribution > 0 else protective).append(d)
    drivers.sort(key=lambda d: -d.contribution)
    protective.sort(key=lambda d: d.contribution)
    return ModelOutput(logistic(logit), logit, drivers, protective, features)
