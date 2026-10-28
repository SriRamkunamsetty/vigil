# SPDX-License-Identifier: Apache-2.0
r"""Multilingual social-engineering lexicon (English, Hindi, Telugu).

Each entry is ``(category, weight, regex)``. ``weight`` is the strength of a
single match in [0, 1] and is combined across matches with a noisy-OR. Patterns
are written for text that has been through :func:`normalize` (NFKC, zero-width
joiners removed, lower-cased, Indic digits mapped to ASCII). Latin patterns use
``\\b``; Indic patterns do not, because ``\\b`` is unreliable around combining
marks.

Romanised Hindi ("Hinglish") and Telugu ("Tenglish") are covered because most
real chat and call-transcript text is written that way.

The lexicon is deliberately a *transparent first layer*: every hit is shown to
the user and to auditors. The Gemini semantic layer (when enabled) handles
paraphrase; this layer keeps the system useful, fast and explainable offline.
Native-speaker review of the Hindi and Telugu entries is recommended before any
production use.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from vigil.domain.models import Category as C

# Categories where "never share your OTP"-style advisories must not count.
NEGATION_SENSITIVE = frozenset(
    {C.CREDENTIAL, C.REMOTE_ACCESS, C.PAYMENT, C.SAFE_ACCOUNT, C.INVESTMENT}
)

# Long-range English cues ("never share ... your OTP") and short-range
# Hindi/Telugu/Hinglish cues, which only negate a directly adjacent request.
# "don't worry, just tell me the OTP" is a scammer's line, not an advisory, so
# negations followed by worry/hesitate/etc. do not count.
_NEG_FAR = re.compile(
    r"(?:\bnever\b|\bdo not\b|\bdon'?t\b|\bdont\b|\bshould not\b|\bshouldn'?t\b|"
    r"\bmust not\b|\bwon'?t\b|\bwill not\b|\bno one\b|\bnobody\b|\bavoid\b|"
    r"\bbeware\b|\bwarning\b|\bbe careful\b|\bnever ask\b|\bnot\b|\bcannot\b|"
    r"कभी (?:भी )?(?:नहीं|न)|सावधान|ఎప్పుడూ|ఎప్పటికీ|జాగ్రత్త)"
    r"(?!\s+(?:worry|hesitate|panic|delay|be afraid|think|ignore|forget|miss|waste))"
)
_NEG_NEAR = re.compile(r"(?:\bmat\b|\bnahi\b|\bna karein\b|\bkabhi\b|मत |వద్దు)")
_SENTENCE_BREAK = re.compile(r"[.!?;:।]")
_CRED_TERMS = re.compile(
    r"otp|\bpin\b|cvv|password|passcode|ओटीपी|पिन|सीवीवी|पासवर्ड|ఓటీపీ|పిన్|సీవీవీ|పాస్వర్డ్"
)


@dataclass(frozen=True)
class Entry:
    """A compiled lexicon entry."""

    pid: int
    category: C
    weight: float
    pattern: re.Pattern[str]


_ZW = dict.fromkeys(map(ord, "‌‍​⁠"), None)
_DIGITS = {
    **{ord("०") + i: ord("0") + i for i in range(10)},
    **{ord("౦") + i: ord("0") + i for i in range(10)},
}


def normalize(text: str) -> str:
    """Normalises text for matching (NFKC, no zero-width marks, lower-case)."""
    t = unicodedata.normalize("NFKC", text).translate(_ZW).translate(_DIGITS).lower()
    return re.sub(r"\s+", " ", t).strip()


_RAW: list[tuple[C, float, str]] = []


def _p(category: C, weight: float, *patterns: str) -> None:
    for pat in patterns:
        _RAW.append((category, weight, pat))


# --- Authority impersonation (law enforcement / regulators) -------------------
_p(C.AUTHORITY, 0.70, r"\b(?:cbi|central bureau of investigation)\b", r"सीबीआई", r"సీబీఐ")
_p(
    C.AUTHORITY,
    0.55,
    r"\b(?:police|cyber ?(?:crime|cell)|crime branch|sub[- ]?inspector|inspector|dcp|ips officer)\b",
    r"पुलिस",
    r"इंस्पेक्टर",
    r"साइबर (?:क्राइम|सेल)",
    r"పోలీస్|పోలీసు",
    r"ఇన్స్పెక్టర్",
    r"సైబర్ క్రైమ్",
)
_p(
    C.AUTHORITY,
    0.65,
    r"\b(?:narcotics|ncb|customs (?:officer|department)|enforcement directorate|income tax (?:officer|department))\b",
    r"\b(?:ed|ncb) (?:officer|office|notice)\b",
    r"नारकोटिक्स",
    r"प्रवर्तन निदेशालय",
    r"నార్కోటిక్స్",
)
_p(
    C.AUTHORITY,
    0.50,
    r"\b(?:trai|department of telecommunications)\b",
    r"ट्राई",
    r"ట్రాయ్",
    r"कस्टम",
    r"కస్టమ్స్",
)
_p(
    C.AUTHORITY,
    0.45,
    r"\b(?:supreme court|high court|court order|magistrate)\b",
    r"अदालत|कोर्ट",
    r"కోర్టు",
)
_p(
    C.AUTHORITY,
    0.40,
    r"\b(?:govt?\.?|government) (?:officer|official)\b",
    r"\brbi (?:officer|official|inspector)\b",
)
_p(C.AUTHORITY, 0.30, r"अधिकारी", r"అధికారి", r"\badhikari\b")

# --- Claiming to be the user's bank -------------------------------------------
_p(
    C.BANK_CLAIM,
    0.35,
    r"\b(?:calling|speaking|call) (?:from|with) (?:the )?(?:\w+ )?bank\b",
    r"\bbank (?:manager|executive|official|representative|customer care)\b",
    r"\b(?:sbi|hdfc|icici|axis|kotak|pnb) (?:bank )?(?:customer care|officer|executive|manager)\b",
    r"\bbank se (?:bol|call)",
    r"बैंक (?:मैनेजर|अधिकारी|से बोल)",
    r"బ్యాంక్ (?:మేనేజర్|అధికారి|నుండి)",
)

# --- Threats: arrest, case, legal harm ----------------------------------------
_p(C.THREAT, 0.95, r"\bdigital arrest\b", r"डिजिटल अर[ेै]स्ट", r"డిజిటల్ అరెస్ట్|డిజిటల్ అరెస్టు")
_p(
    C.THREAT,
    0.55,
    r"\barrest warrant\b",
    r"\bwarrant\b",
    r"\b(?:will be|get|getting|been) arrested\b",
    r"\barrest(?:ed)?\b",
    r"\bgiraft[a-z]*\b",
    r"गिरफ़?्तार",
    r"वारंट",
    r"అరెస్ట్|అరెస్టు",
    r"వారెంట్",
    r"\barrest chest",
)
_p(C.THREAT, 0.60, r"\bmoney laundering\b", r"मनी लॉन्ड्रिंग|मनी लांडरिंग", r"మనీ లాండరింగ్")
_p(
    C.THREAT,
    0.55,
    r"\b(?:fir|case) (?:has been |will be |is )?(?:registered|filed|lodged)\b",
    r"\b(?:fir|case) darj\b",
    r"एफआईआर",
    r"केस दर्ज|मुकदमा",
    r"ఎఫ్ఐఆర్",
    r"కేసు (?:నమోదు|పెట్టు|పడ)",
    r"\bcase pad",
)
_p(
    C.THREAT,
    0.70,
    r"\bdrugs? (?:found|in (?:the|your) (?:parcel|package))\b",
    r"\billegal (?:items?|parcel|drugs?|activity|goods)\b",
    r"ड्रग्स|नशीला",
    r"డ్రగ్స్",
)
_p(
    C.THREAT,
    0.55,
    r"\bunder (?:investigation|surveillance)\b",
    r"\bjail\b",
    r"जेल",
    r"జైలు",
    r"\bassets? (?:will be )?(?:seized|frozen)\b",
    r"\blegal action\b",
)

# --- Secrecy / isolation (the hallmark of coercive scams) ---------------------
_p(
    C.SECRECY,
    0.85,
    r"\b(?:do not|don'?t|dont|never) (?:tell|inform|share this with|disclose|talk to) (?:anyone|anybody|your family|family|others|the bank|any one)\b",
    r"\bkisi ko (?:bhi )?(?:mat|na|nahi) (?:batana|batao|bataye|bataiye|batayen)\b",
    r"किसी को (?:भी )?(?:मत|न|नहीं) (?:बताना|बताएं|बताइए|बताओ)",
    r"घर वालों को (?:मत|न|नहीं)",
    r"\b(?:ghar|family) (?:walon|walo) ko (?:mat|na|nahi)\b",
    r"ఎవరికీ (?:చెప్పొద్దు|చెప్పవద్దు|చెప్పకండి|చెప్పకూడదు)",
    r"కుటుంబ సభ్యులకు (?:చెప్పొద్దు|చెప్పవద్దు|చెప్పకండి)",
    r"\bevariki (?:cheppakandi|cheppoddu|cheppakudadu|cheppavaddu)\b",
    r"\bfamily ki (?:cheppakandi|cheppoddu)\b",
)
_p(
    C.SECRECY,
    0.80,
    r"\b(?:do not|don'?t|dont) (?:disconnect|cut|hang up|end) (?:the )?(?:call|phone|line)\b",
    r"\bkeep (?:this|it) (?:secret|confidential)\b",
    r"\b(?:do not|don'?t|dont) (?:contact|call) (?:your )?(?:family|lawyer)\b",
    r"\bcall (?:mat|na|nahi) (?:kaat|kato|katna|kaatna|kaatiye|katiye|rakhna)",
    r"\bphone (?:mat|na) (?:kaat|rakh)",
    r"(?:फोन|कॉल) (?:मत|न) (?:काट|कटना|काटना|काटें|रखना|रखें)",
    r"కాల్ (?:కట్|కట్టు|ఆపు|డిస్కనెక్ట్) ?(?:చేయకండి|చేయవద్దు|చేయకూడదు|చెయ్యొద్దు)",
    r"ఫోన్ (?:పెట్టేయకండి|పెట్టేయవద్దు|కట్ చేయకండి)",
    r"\bcall cut (?:cheyakandi|cheyoddu|cheyakudadu|cheyavaddu)\b",
)
_p(
    C.SECRECY,
    0.75,
    r"\b(?:do not|don'?t|dont) (?:visit|go to) (?:the )?(?:bank|branch|police station)\b",
    r"\bbank (?:mat|na) (?:jaana|jana|jao)\b",
    r"बैंक (?:मत|न) जा",
    r"బ్యాంక్ ?కి వెళ్ళ(?:కండి|వద్దు)",
)
_p(
    C.SECRECY,
    0.60,
    r"\bconfidential (?:case|matter|investigation)\b",
    r"गोपनीय",
    r"రహస్యం",
    r"\bnational security\b",
)
_p(C.SECRECY, 0.55, r"\bstay on (?:the )?(?:line|call)\b")

# --- Urgency -------------------------------------------------------------------
_p(
    C.URGENCY,
    0.40,
    r"\b(?:immediately|right now|at once|urgent(?:ly)?|asap)\b",
    r"\b(?:turant|fauran|abhi ke abhi|jaldi|jald se jald|ventane|ippude|twaraga|tvaraga|takshanam)\b",
    r"तुरंत|फौरन|जल्दी|जल्द से जल्द",
    r"వెంటనే|తక్షణమే|ఇప్పుడే|త్వరగా",
)
_p(
    C.URGENCY,
    0.50,
    r"\bwithin (?:the next )?\d+ ?(?:minutes?|mins?|hours?|hrs?)\b",
    r"\b(?:last|final) (?:chance|warning|notice)\b",
    r"\bbefore (?:it'?s|it is) too late\b",
    r"\d+ ?(?:मिनट|घंटे) (?:के अंदर|में)",
    r"आखिरी (?:मौका|चेतावनी)",
    r"\d+ ?(?:నిమిషా|గంటల)",
    r"చివరి (?:అవకాశం|హెచ్చరిక)",
    r"\b\d+ (?:minute|ghante|nimishala|gantala)\w* ?(?:ke andar|mein|lo)\b",
)
_p(C.URGENCY, 0.25, r"\babhi\b", r"अभी")

# --- Credential requests (OTP / PIN / CVV / password) --------------------------
_p(
    C.CREDENTIAL,
    0.85,
    r"\b(?:share|send|tell|give|provide|read out|forward|enter|confirm) (?:me |us |them )?(?:your |the |that |this )?(?:otp|one[- ]time password|upi pin|pin|cvv|card number|password|mpin|passcode)\b",
    r"\b(?:otp|pin|cvv|password|mpin) (?:bata(?:o|iye|ye|na)?|batayen|bataiye|share kar(?:o|iye|na)?|bhej(?:o|iye|na)?|de(?:do|dijiye|na)?|bolo|boliye)\b",
    r"\b(?:otp|pin|cvv|mpin)\b[^.!?\n]{0,45}\b(?:mujhe|humein|hamein|mereko) (?:abhi |turant |jaldi )?(?:bata(?:o|iye|ye)|bol(?:o|iye)|bhej(?:o|iye)|de(?:do|dijiye))\b",
    r"(?:ओटीपी|पिन|सीवीवी|पासवर्ड|एमपिन) (?:बताइए|बताओ|बताएं|दीजिए|दो|शेयर|भेजिए|भेजो|बोलिए)",
    r"(?:ఓటీపీ|పిన్|సీవీవీ|పాస్వర్డ్|ఎంపిన్) (?:చెప్పండి|చెప్పు|ఇవ్వండి|షేర్ చేయండి|పంపండి|చెప్పాలి)",
    r"\b(?:otp|pin|cvv|password) (?:cheppandi|cheppu|ivvandi|share cheyandi|pampandi|cheppali)\b",
    r"(?:ओटीपी|पिन) (?:डालिए|डालो|दर्ज करें|दर्ज कीजिए)",
    r"(?:ఓటీపీ|పిన్) (?:ఎంటర్ చేయండి|నమోదు చేయండి)",
)
_p(
    C.CREDENTIAL,
    0.60,
    r"\b(?:otp|pin|code) (?:you (?:got|received)|received|sent to)\b",
    r"\botp (?:aaya|aya|aaye)\b",
    r"(?:ओटीपी|पिन|पासवर्ड) (?:आया|आए)",
    r"ఓటీపీ (?:వచ్చింది|వచ్చిందా)",
    r"\botp (?:vacchindi|vachindi)\b",
)
_p(C.CREDENTIAL, 0.15, r"\b(?:otp|cvv|upi pin|mpin)\b", r"ओटीपी", r"ఓటీపీ")

# --- Remote access / malicious app installs ------------------------------------
_p(
    C.REMOTE_ACCESS,
    0.75,
    r"\b(?:anydesk|any desk|teamviewer|team viewer|quick ?support|rustdesk|airdroid)\b",
    r"\bshare your screen\b",
    r"\bscreen ?shar(?:e|ing)\b",
    r"\bremote access\b",
    r"\.apk\b",
    r"एनीडेस्क|टीमव्यूअर|क्विक ?सपोर्ट|स्क्रीन शेयर|रिमोट",
    r"ఎనీడెస్క్|టీమ్ ?వ్యూయర్|స్క్రీన్ షేర్|రిమోట్",
    r"\bscreen share (?:kar|cheya)",
)
_p(
    C.REMOTE_ACCESS,
    0.55,
    r"\b(?:install|download|open) (?:this |the |an? )?(?:app|application|software|link)\b",
    r"\b(?:download|install) (?:kar(?:o|iye|na)?|kijiye|cheya(?:ndi|mani|ali))\b",
    r"(?:ऐप|ऐप्प|एप्लिकेशन|एपीके|लिंक) ?(?:डाउनलोड|इंस्टॉल|खोल|क्लिक)",
    r"(?:యాప్|లింక్|ఏపీకే)\S{0,3} ?(?:డౌన్లోడ్|ఇన్స్టాల్|క్లిక్)",
)
_p(C.REMOTE_ACCESS, 0.35, r"\b(?:click|tap|open) (?:on )?(?:the |this )?link\b")

# --- KYC / account-block pretexts ---------------------------------------------
_p(
    C.KYC_BLOCK,
    0.60,
    r"\bkyc (?:is |has )?(?:expired|pending|incomplete|not updated|update|expire)\b",
    r"\bupdate (?:your )?(?:kyc|pan|aadhaar)\b",
    r"\byour (?:sim|number) (?:will be|is going to be) (?:blocked|disconnected)\b",
    r"\b(?:electricity|power) (?:will be )?(?:cut|disconnected)\b",
    r"\bbijli (?:kat|kaat)",
    r"केवाईसी (?:एक्सपायर|अपडेट|पेंडिंग|पूरा)",
    r"बिजली (?:कट|काट)",
    r"కేవైసీ ?(?:అప్డేట్|ఎక్స్పైర్|పెండింగ్)",
    r"(?:విద్యుత్|కరెంట్) (?:కట్|నిలిపివేత)",
    r"\bkyc update cheyali\b",
)
_p(
    C.KYC_BLOCK,
    0.55,
    r"\b(?:account|card|sim|number|upi|wallet) (?:will be |has been |is being |got )(?:blocked|suspended|deactivated|frozen|closed|disconnected)\b",
    r"\b(?:account|sim|card|number) (?:band|block) ho (?:jayega|jaega|jaye|jayegi)\b",
    r"(?:खाता|अकाउंट|कार्ड|सिम|नंबर) (?:बंद|ब्लॉक|बन्द|सस्पेंड)",
    r"(?:ఖాతా|అకౌంట్|కార్డ్|సిమ్|నంబర్) (?:బ్లాక్|క్లోజ్|ఆగిపో|నిలిపివేయ|డీయాక్టివేట్)",
    r"\b(?:account|sim|card|number) block (?:avutundi|ayipotundi|avthundi)\b",
)

# --- Safe-account / refundable-deposit transfers --------------------------------
_p(
    C.SAFE_ACCOUNT,
    0.90,
    r"\bsafe account\b",
    r"सुरक्षित (?:खाते|खाता|अकाउंट)",
    r"సేఫ్ అకౌంట్|సురక్షిత (?:ఖాతా|అకౌంట్)",
    r"\b(?:transfer|deposit|send|move) .{0,40}(?:to|into) .{0,15}(?:secure|rbi|government|verification|escrow|holding|temporary) account\b",
)
_p(
    C.SAFE_ACCOUNT,
    0.75,
    r"\brbi (?:verification|account|ke account)\b",
    r"आरबीआई (?:खाते|खाता|अकाउंट)",
    r"ఆర్బీఐ (?:అకౌంట్|ఖాతా)",
    r"\brbi account\b",
)
_p(
    C.SAFE_ACCOUNT,
    0.65,
    r"\b(?:verification|refundable|security) (?:amount|deposit|fee)\b",
    r"\b(?:verification|jaanch) (?:ke liye|amount)\b",
    r"\bverification kosam\b",
    r"(?:वेरिफिकेशन|सत्यापन) (?:के लिए|राशि|अमाउंट)",
    r"(?:వెరిఫికేషన్|ధృవీకరణ) (?:కోసం|మొత్తం|అమౌంట్)",
)
_p(
    C.SAFE_ACCOUNT,
    0.60,
    r"\b(?:will be|shall be|would be) (?:refunded|returned|reversed)(?: to you| back)? (?:after|once|within)\b",
    r"\b(?:wapas|vapas|refund) (?:ho jayega|kar diye jayenge|mil jayega|kar denge)\b",
    r"(?:वापस|रिफंड) (?:कर दिया जाएगा|कर दिए जाएंगे|मिल जाएंगे|हो जाएगा)",
    r"(?:తిరిగి|వాపస్|రిఫండ్) (?:ఇస్తాం|ఇచ్చేస్తాం|చేస్తాం|వస్తాయి)",
    r"\b(?:tirigi|waapas|refund) (?:istam|ichestam|chestam|vastayi)\b",
)

# --- Prize / refund / fee bait ---------------------------------------------------
_p(
    C.PRIZE_REFUND,
    0.85,
    r"\bwon (?:a |the )?(?:lottery|prize|lucky draw|jackpot|reward|iphone)\b",
    r"\benter (?:your )?upi pin to (?:receive|get|claim)\b",
    r"\bpaise (?:pane|lene) ke liye (?:upi )?pin\b",
    r"(?:पैसे|पैसा) (?:पाने|लेने) के लिए (?:अपना )?(?:यूपीआई )?पिन",
    r"డబ్బు (?:పొందాలంటే|రావాలంటే) .{0,20}పిన్",
)
_p(
    C.PRIZE_REFUND,
    0.65,
    r"\b(?:processing|registration|release|clearance|customs) fee\b",
    r"प्रोसेसिंग फीस|रजिस्ट्रेशन फीस",
    r"ప్రాసెసింగ్ ఫీజు|రిజిస్ట్రేషన్ ఫీజు",
    r"\bclaim (?:your )?(?:prize|reward|refund)\b",
)
_p(
    C.PRIZE_REFUND,
    0.70,
    r"\b(?:lottery|lucky draw|jackpot|inaam|bahumati)\b",
    r"लॉटरी|इनाम|लकी ड्रा|जैकपॉट",
    r"లాటరీ|బహుమతి|లక్కీ డ్రా|జాక్పాట్",
)
_p(
    C.PRIZE_REFUND,
    0.50,
    r"\b(?:pending|unclaimed) refund\b",
    r"\b(?:tax|income tax|gst|insurance|order) refund\b",
    r"\brefund (?:pending|aane wala|ravali)\b",
)
_p(C.PRIZE_REFUND, 0.45, r"रिफंड", r"రీఫండ్")
_p(C.PRIZE_REFUND, 0.35, r"\bcashback\b", r"कैशबैक")

# --- Guaranteed returns / task-job / tipster schemes -----------------------------
_p(
    C.INVESTMENT,
    0.85,
    r"\bguaranteed (?:returns?|profits?|income)\b",
    r"\b(?:double|triple|10x) (?:your )?(?:money|investment)\b",
    r"\bpaise (?:double|dugne)\b",
    r"\bpakka (?:munafa|return)\b",
    r"\bdabbulu (?:double|rettimpu)\b",
    r"(?:गारंटीड|पक्का) (?:रिटर्न|मुनाफा)",
    r"पैसे (?:दोगुने|डबल)",
    r"గ్యార(?:ె|ం)టీ (?:రిటర్న్స్|రిటర్న్|లాభం|ఆదాయం)",
    r"నష్టం (?:అసలు )?(?:ఉండదు|రాదు)",
    r"(?:రోజుకు|నెలకు|వారానికి) \d+ ?% (?:గ్యార|రిటర్న్|లాభం)",
    r"డబ్బు (?:రెట్టింపు|డబుల్)",
)
_p(C.INVESTMENT, 0.80, r"\b\d+ ?% (?:returns?|profit) (?:per|a|every) (?:day|week|month)\b")
_p(
    C.INVESTMENT,
    0.70,
    r"\b(?:daily|weekly|monthly) (?:returns?|profits?|income) of \d+",
    r"\binsider (?:tip|information|trading)\b",
    r"\btask[- ]based (?:job|earning)\b",
    r"\bipo allotment (?:guaranteed|assured)\b",
)
_p(
    C.INVESTMENT,
    0.60,
    r"\b(?:risk[- ]free|no risk|bina risk|risk lekunda)\b",
    r"बिना (?:रिस्क|जोखिम)",
    r"రిస్క్ లేకుండా",
    r"\b(?:vip|premium|special) (?:trading |stock |investment )?(?:group|channel|tips)\b",
    r"\bjoin (?:our|my) (?:whatsapp|telegram) (?:group|channel)\b",
    r"\bwork from home.{0,20}(?:earn|income)\b",
)
_p(
    C.INVESTMENT,
    0.50,
    r"व्हाट्सएप ग्रुप|टेलीग्राम ग्रुप",
    r"వాట్సాప్ గ్రూప్|టెలిగ్రామ్ గ్రూప్",
    r"రోజువారీ ఆదాయం",
    r"\bdaily (?:kamai|income)\b",
)
_p(C.INVESTMENT, 0.35, r"\b(?:crypto|bitcoin|usdt|forex) (?:trading|investment|scheme)\b")

# --- Courier / customs / "your Aadhaar was used" pretext ------------------------
_p(
    C.COURIER,
    0.75,
    r"\b(?:passports?|drugs?|mdma|narcotics|illegal items?) .{0,30}(?:found|detected|recovered|inside)\b",
)
_p(
    C.COURIER,
    0.70,
    r"\b(?:parcel|package|consignment|shipment) (?:is |has been )?(?:held|seized|stuck|detained|intercepted|blocked)\b",
    r"\b(?:your )?(?:aadhaar|pan|sim) (?:is |was |has been )?(?:linked|used|found) (?:in|to|with)\b",
)
_p(
    C.COURIER,
    0.60,
    r"\bparcel .{0,30}(?:taiwan|thailand|china|dubai|iran|malaysia|singapore)\b",
    r"आधार (?:से )?लिंक",
    r"ఆధార్ (?:తో )?లింక్",
    r"\baadhaar (?:se )?link",
    r"\baadhaar link ayyindi\b",
)
_p(
    C.COURIER,
    0.50,
    r"\bcustoms (?:clearance|duty)\b",
    r"(?:पार्सल|कूरियर|पैकेज) (?:में|से|पकड़ा|रोका|जब्त)",
    r"(?:పార్సిల్|కొరియర్|ప్యాకేజీ) (?:లో|నుండి|పట్టుబడ|ఆపేశా|సీజ్)",
    r"\b(?:parcel|courier|package) (?:mein|se|pakda|roka|jabt)\b",
)
_p(
    C.COURIER,
    0.45,
    r"\b(?:fedex|dhl|blue ?dart|india post|courier) .{0,40}(?:parcel|package|consignment|shipment)\b",
)
_p(C.COURIER, 0.40, r"फेडेक्स|डीएचएल", r"ఫెడెక్స్|డీహెచ్ఎల్", r"\b(?:fedex|dhl)\b")

# --- Family-emergency / voice-clone pretext -------------------------------------
_p(
    C.FAMILY,
    0.80,
    r"\b(?:it'?s|this is) (?:me|your (?:son|daughter|nephew|grandson|grandchild|brother|friend))\b.{0,40}(?:trouble|accident|hospital|arrested|police|jail|emergency|stuck)",
)
_p(
    C.FAMILY,
    0.70,
    r"\bsend (?:me )?money (?:urgently|immediately|right now|asap)\b",
    r"\b(?:papa|dad|mom|mummy|grandpa|dadi|nani|nana) (?:it'?s|this is) me\b",
)
_p(
    C.FAMILY,
    0.60,
    r"\b(?:papa|mummy|dada|dadi|nana|nani)[, ]*main (?:bol|hoon|hun)\b",
    r"(?:पापा|मम्मी|दादा|दादी|नाना|नानी|मामा|चाचा)[, ]*मैं (?:बोल|हूँ|हूं)",
    r"(?:నాన్న|అమ్మ|తాత|అమ్మమ్మ|నానమ్మ)[, ]*నేను",
    r"\b(?:nanna|amma|thatha)[, ]*nenu\b",
)
_p(C.FAMILY, 0.50, r"\bbail\b|जमानत|బెయిల్|\bjamanat\b")
_p(C.FAMILY, 0.45, r"\b(?:medical emergency|hospital bill|in (?:an )?accident)\b")
_p(
    C.FAMILY,
    0.40,
    r"\b(?:accident|hospital)\b",
    r"एक्सीडेंट|अस्पताल|हॉस्पिटल",
    r"యాక్సిడెంట్|ఆసుపత్రి|హాస్పిటల్",
    r"\b(?:my phone|phone) (?:is )?(?:broken|lost|damaged)\b",
)
_p(
    C.FAMILY,
    0.35,
    r"\bnew number\b",
    r"\bnaya number\b",
    r"नया नंबर",
    r"\bkotha number\b",
    r"కొత్త నంబర్",
)

# --- Instruction to move money -----------------------------------------------------
_p(
    C.PAYMENT,
    0.70,
    r"\b(?:transfer|send|pay|deposit|remit|wire|move) (?:the |an? )?(?:\w+ )?(?:amount|money|funds|rs\.?|rupees|inr|₹|\d)",
    r"\b(?:transfer|send|pay|bhej|bhejo|jama) (?:kar(?:o|iye|na|ein)?|kijiye|do|dijiye)\b",
    r"\b(?:paise|paisa|amount|rakam|rupay[ae]|dabbulu|money) .{0,20}(?:bhej|transfer|jama|pampandi|pay)",
    r"\b(?:transfer|pay|send|pampandi|pampinchandi) (?:cheyandi|cheyali|cheyyi|cheyyandi)\b",
    r"(?:ट्रांसफर|भेज|जमा|पेमेंट|भुगतान) ?(?:कर|करें|कीजिए|करो|दीजिए|दो)\b",
    r"(?:पैसे|रकम|राशि|रुपये|₹) .{0,20}(?:भेज|ट्रांसफर|जमा)",
    r"(?:ట్రాన్స్ఫర్|పంపండి|పంపించండి|చెల్లించండి|పేమెంట్) ?(?:చేయండి|చేయాలి|చెయ్యి)?",
    r"(?:డబ్బు|మొత్తం|రూపాయలు|అమౌంట్) .{0,20}(?:పంపండి|పంపించండి|ట్రాన్స్ఫర్|జమ)",
)
_p(C.PAYMENT, 0.60, r"\bmake (?:the |a )?payment\b", r"\bpayment (?:kar(?:o|iye)|cheyandi)\b")
_p(
    C.PAYMENT,
    0.50,
    r"\b(?:upi|neft|rtgs|imps|phonepe|gpay|google pay|paytm) .{0,25}(?:transfer|send|pay)\b",
    r"\bpampandi\b",
)
_p(
    C.PAYMENT,
    0.45,
    r"\b(?:scan|open) (?:this |the )?qr\b",
    r"\bqr code scan\b",
    r"क्यूआर कोड",
    r"క్యూఆర్ కోడ్",
)
_p(C.PAYMENT, 0.25, r"(?:₹|\brs\.?|\binr)\s?[\d,]{4,}")

# --- Attempts to manipulate an AI reviewer (call transcripts are attacker-controlled)
_p(
    C.INJECTION,
    0.90,
    r"\bignore (?:all |any )?(?:previous|prior|above|earlier) (?:instructions?|prompts?|rules?)\b",
    r"\b(?:tell|say to|inform) the user (?:that )?(?:this|it|the (?:call|payment|transfer)) (?:is )?(?:safe|legit(?:imate)?|genuine|verified|fine)\b",
    r"\bmark (?:this|it) as (?:safe|legit|genuine|verified|low risk)\b",
    r"\boverride (?:the )?(?:safety|security|fraud) (?:check|rules?|filters?)\b",
    r"पिछले निर्देश(?:ों)? (?:को )?(?:अनदेखा|नज़रअंदाज़)",
    r"మునుపటి సూచనలను (?:విస్మరించు|పట్టించుకోకు)",
)
_p(
    C.INJECTION,
    0.80,
    r"\b(?:do not|don'?t) (?:flag|warn|alert|block)\b",
    r"\bdisregard (?:the )?(?:above|previous)\b",
)
_p(
    C.INJECTION,
    0.70,
    r"\byou are now (?:an? |the |in )?(?:ai|assistant|chatbot|bot|developer mode|dan|unrestricted|jailbroken)\b",
    r"\bsystem prompt\b",
)


def _compile() -> list[Entry]:
    entries: list[Entry] = []
    for pid, (cat, weight, pat) in enumerate(_RAW):
        entries.append(
            Entry(pid, cat, weight, re.compile(unicodedata.normalize("NFKC", pat), re.IGNORECASE))
        )
    return entries


ENTRIES: list[Entry] = _compile()


def is_negated(text: str, start: int) -> bool:
    """Returns True if a negation/advisory cue governs the match at ``start``.

    English cues count within the same sentence (max 60 characters back);
    Hindi/Telugu/Hinglish cues only within 14, so "call mat kaatna ... paise
    transfer karo" is not negated.
    """
    far = text[max(0, start - 60) : start]
    last_break = max((m.end() for m in _SENTENCE_BREAK.finditer(far)), default=0)
    return bool(
        _NEG_FAR.search(far[last_break:]) or _NEG_NEAR.search(text[max(0, start - 14) : start])
    )


def is_credential_advisory(text: str, start: int, end: int) -> bool:
    """True if a "don't tell anyone" match is really "don't share your OTP/PIN"."""
    return bool(_CRED_TERMS.search(text[max(0, start - 30) : end + 30]))
