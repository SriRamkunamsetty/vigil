# SPDX-License-Identifier: Apache-2.0
"""Plain-language, multilingual intervention templates.

These are the safe default. When Gemini is enabled it may rewrite the text for
the specific situation, but its output is validated against these templates'
constraints (see ``vigil.agents.composer``). Hindi and Telugu strings should be
reviewed by native speakers before production use.
"""

from __future__ import annotations

from vigil.domain.models import Intervention, Language, ScamType, Tier

L = Language
S = ScamType

_HELPLINE = {
    L.EN: "Report at 1930 (National Cyber Crime Helpline) or cybercrime.gov.in.",
    L.HI: "1930 (राष्ट्रीय साइबर क्राइम हेल्पलाइन) पर कॉल करें या cybercrime.gov.in पर शिकायत करें।",
    L.TE: "1930 (జాతీయ సైబర్ క్రైమ్ హెల్ప్‌లైన్)కి కాల్ చేయండి లేదా cybercrime.gov.in లో ఫిర్యాదు చేయండి.",
}

_HOLD_STEP = {
    L.EN: "We have paused this payment. A bank officer will confirm with you on your registered number.",
    L.HI: "हमने यह भुगतान रोक दिया है। बैंक का अधिकारी आपके रजिस्टर्ड नंबर पर आपसे पुष्टि करेगा।",
    L.TE: "ఈ చెల్లింపును నిలిపివేశాం. బ్యాంక్ అధికారి మీ రిజిస్టర్డ్ నంబర్‌కు కాల్ చేసి నిర్ధారిస్తారు.",
}

_GENERIC = {
    L.EN: (
        "Take a moment before you pay.",
        "This payment looks unusual for you. Check who you are paying and why before sending.",
        [
            "Confirm the receiver through a number you already trust.",
            "If anyone is pressuring you to hurry, stop and talk to someone you trust.",
        ],
    ),
    L.HI: (
        "भुगतान से पहले एक पल रुकिए।",
        "यह भुगतान आपके लिए असामान्य लगता है। भेजने से पहले जांच लें कि आप किसे और क्यों पैसे दे रहे हैं।",
        [
            "जिस नंबर पर आपको पहले से भरोसा है, उसी से पाने वाले की पुष्टि करें।",
            "अगर कोई जल्दी करने का दबाव डाल रहा है, तो रुककर किसी भरोसेमंद व्यक्ति से बात करें।",
        ],
    ),
    L.TE: (
        "చెల్లించే ముందు ఒక్క క్షణం ఆగండి.",
        "ఈ చెల్లింపు మీకు అసాధారణంగా కనిపిస్తోంది. పంపే ముందు ఎవరికి, ఎందుకు ఇస్తున్నారో సరిచూసుకోండి.",
        [
            "మీకు ఇప్పటికే నమ్మకమైన నంబర్ ద్వారా అందుకునే వారిని నిర్ధారించుకోండి.",
            "ఎవరైనా తొందర పెడుతుంటే ఆగి, నమ్మకమైన వారితో మాట్లాడండి.",
        ],
    ),
}

_TEMPLATES: dict[ScamType, dict[Language, tuple[str, str, list[str]]]] = {
    S.DIGITAL_ARREST: {
        L.EN: (
            "Stop. This looks like a 'digital arrest' scam.",
            "No real police officer, CBI or court arrests anyone over a phone or video call, or asks for money to 'verify' or 'clear' you. The caller is trying to scare you and keep you isolated.",
            [
                "Hang up. You are not under arrest.",
                "Do not send money or share OTPs, PINs or documents.",
                "Tell a family member or friend right now.",
            ],
        ),
        L.HI: (
            "रुकिए! यह 'डिजिटल अरेस्ट' ठगी है।",
            "असली पुलिस, सीबीआई या कोर्ट फोन या वीडियो कॉल पर किसी को गिरफ्तार नहीं करते और न ही 'जांच' या 'क्लियरेंस' के नाम पर पैसे मांगते हैं। सामने वाला आपको डराकर अकेला रखना चाहता है।",
            [
                "कॉल काट दीजिए। आप गिरफ्तार नहीं हैं।",
                "कोई पैसा न भेजें, और OTP, PIN या दस्तावेज़ साझा न करें।",
                "अभी किसी घरवाले या दोस्त को बताइए।",
            ],
        ),
        L.TE: (
            "ఆగండి! ఇది 'డిజిటల్ అరెస్ట్' మోసం.",
            "నిజమైన పోలీసులు, సీబీఐ లేదా కోర్టు ఫోన్ లేదా వీడియో కాల్‌లో ఎవరినీ అరెస్ట్ చేయరు, 'దర్యాప్తు' లేదా 'క్లియరెన్స్' పేరుతో డబ్బు అడగరు. అవతలి వ్యక్తి మిమ్మల్ని భయపెట్టి, ఒంటరిగా ఉంచాలని చూస్తున్నాడు.",
            [
                "కాల్ కట్ చేయండి. మీరు అరెస్ట్ కాలేదు.",
                "డబ్బు పంపవద్దు; OTP, PIN లేదా పత్రాలు షేర్ చేయవద్దు.",
                "ఇప్పుడే కుటుంబ సభ్యులకు లేదా స్నేహితులకు చెప్పండి.",
            ],
        ),
    },
    S.KYC_OTP: {
        L.EN: (
            "Stop. Banks never ask for your OTP or PIN.",
            "Someone is using a KYC or 'account will be blocked' scare to get your OTP, PIN or to make you install an app.",
            [
                "Never share OTP, PIN or CVV with anyone.",
                "Hang up and call the number printed on your card or use your bank's official app.",
                "Do not install any app or tap any link they send.",
            ],
        ),
        L.HI: (
            "रुकिए! बैंक कभी आपका OTP या PIN नहीं मांगता।",
            "KYC या खाता बंद होने का डर दिखाकर आपसे OTP, PIN लेने या ऐप इंस्टॉल कराने की कोशिश हो रही है।",
            [
                "OTP, PIN या CVV किसी को न बताएं।",
                "कॉल काटकर अपने कार्ड के पीछे छपे नंबर पर या बैंक के आधिकारिक ऐप से बात करें।",
                "उनके भेजे कोई ऐप या लिंक इंस्टॉल/क्लिक न करें।",
            ],
        ),
        L.TE: (
            "ఆగండి! బ్యాంక్ ఎప్పుడూ మీ OTP లేదా PIN అడగదు.",
            "KYC లేదా ఖాతా బ్లాక్ అవుతుందనే భయం చూపి, మీ OTP, PIN తీసుకోవడానికి లేదా యాప్ ఇన్‌స్టాల్ చేయించడానికి ప్రయత్నిస్తున్నారు.",
            [
                "OTP, PIN, CVV ఎవరికీ చెప్పవద్దు.",
                "కాల్ కట్ చేసి, మీ కార్డ్ వెనుక ఉన్న నంబర్‌కు లేదా బ్యాంక్ అధికారిక యాప్ ద్వారా సంప్రదించండి.",
                "వారు పంపిన యాప్ లేదా లింక్‌ను ఇన్‌స్టాల్/క్లిక్ చేయవద్దు.",
            ],
        ),
    },
    S.REMOTE_ACCESS: {
        L.EN: (
            "Stop. Do not let anyone control your phone.",
            "Screen-sharing and remote-support apps let a stranger see your OTPs and move money from your account.",
            [
                "Close the app and disconnect from the call.",
                "Never install apps someone asks you to over the phone.",
                "Call your bank on its official number to check your account.",
            ],
        ),
        L.HI: (
            "रुकिए! किसी को अपना फोन कंट्रोल करने न दें।",
            "स्क्रीन शेयर और रिमोट ऐप से अजनबी आपके OTP देख सकता है और आपके खाते से पैसे निकाल सकता है।",
            [
                "ऐप बंद करें और कॉल काट दें।",
                "फोन पर कहे जाने पर कोई ऐप इंस्टॉल न करें।",
                "अपने बैंक के आधिकारिक नंबर पर कॉल करके खाते की जांच करें।",
            ],
        ),
        L.TE: (
            "ఆగండి! మీ ఫోన్‌ను ఎవరికీ కంట్రోల్ చేయనివ్వకండి.",
            "స్క్రీన్ షేరింగ్, రిమోట్ యాప్‌ల ద్వారా అపరిచితులు మీ OTP చూసి, మీ ఖాతా నుంచి డబ్బు తీసుకోగలరు.",
            [
                "యాప్ మూసేసి కాల్ కట్ చేయండి.",
                "ఫోన్‌లో ఎవరైనా చెప్పారని యాప్‌లు ఇన్‌స్టాల్ చేయవద్దు.",
                "మీ బ్యాంక్ అధికారిక నంబర్‌కు కాల్ చేసి ఖాతాను పరిశీలించండి.",
            ],
        ),
    },
    S.INVESTMENT: {
        L.EN: (
            "Careful. 'Guaranteed returns' is a red flag.",
            "No genuine investment guarantees profit. Pressure to put money in quickly is also a warning sign.",
            [
                "Check the firm on SEBI's website before paying.",
                "Avoid paid tip groups and unknown trading apps.",
                "Wait 24 hours and ask someone you trust.",
            ],
        ),
        L.HI: (
            "सावधान! 'पक्का मुनाफा' ठगी की निशानी है।",
            "कोई भी असली निवेश मुनाफे की गारंटी नहीं देता। जल्दी पैसे लगाने का दबाव भी ठगी का संकेत है।",
            [
                "पैसे लगाने से पहले SEBI की वेबसाइट पर कंपनी जांचें।",
                "पेड टिप ग्रुप या अनजान ऐप में पैसे न डालें।",
                "24 घंटे रुककर किसी भरोसेमंद व्यक्ति से सलाह लें।",
            ],
        ),
        L.TE: (
            "జాగ్రత్త! 'గ్యారెంటీ లాభం' అనేది మోసానికి సంకేతం.",
            "నిజమైన పెట్టుబడి ఏదీ లాభానికి హామీ ఇవ్వదు. త్వరగా డబ్బు పెట్టమని ఒత్తిడి చేయడం కూడా మోసానికి సంకేతం.",
            [
                "డబ్బు పెట్టే ముందు SEBI వెబ్‌సైట్‌లో సంస్థను చెక్ చేయండి.",
                "పెయిడ్ టిప్ గ్రూపులు లేదా తెలియని యాప్‌లలో డబ్బు పెట్టవద్దు.",
                "24 గంటలు ఆగి, నమ్మకమైన వారి సలహా తీసుకోండి.",
            ],
        ),
    },
    S.COURIER_CUSTOMS: {
        L.EN: (
            "Stop. Parcel or customs problems are not solved by paying a person on UPI.",
            "Scammers claim a parcel with illegal items is linked to your Aadhaar or SIM to scare you into paying.",
            [
                "Hang up and check with the courier company's official number.",
                "Do not share Aadhaar details or send money.",
                "Real customs duty is never collected into a personal account.",
            ],
        ),
        L.HI: (
            "रुकिए! पार्सल या कस्टम का मामला UPI से किसी व्यक्ति को पैसे भेजकर नहीं सुलझता।",
            "ठग दावा करते हैं कि गैरकानूनी सामान वाला पार्सल आपके आधार या सिम से जुड़ा है, ताकि आप डरकर पैसे भेज दें।",
            [
                "कॉल काटकर कूरियर कंपनी के आधिकारिक नंबर से जांचें।",
                "आधार की जानकारी न दें और पैसे न भेजें।",
                "असली कस्टम शुल्क किसी निजी खाते में नहीं लिया जाता।",
            ],
        ),
        L.TE: (
            "ఆగండి! పార్సిల్ లేదా కస్టమ్స్ సమస్యను UPI ద్వారా ఒక వ్యక్తికి డబ్బు పంపి పరిష్కరించరు.",
            "చట్టవిరుద్ధ వస్తువులున్న పార్సిల్ మీ ఆధార్ లేదా సిమ్‌తో ముడిపడి ఉందని భయపెట్టి డబ్బు పంపించేలా చేస్తారు.",
            [
                "కాల్ కట్ చేసి కొరియర్ సంస్థ అధికారిక నంబర్‌తో సరిచూసుకోండి.",
                "ఆధార్ వివరాలు ఇవ్వవద్దు, డబ్బు పంపవద్దు.",
                "నిజమైన కస్టమ్స్ సుంకం వ్యక్తిగత ఖాతాలోకి తీసుకోరు.",
            ],
        ),
    },
    S.PRIZE_REFUND: {
        L.EN: (
            "Stop. You never pay to receive money or a prize.",
            "Entering your UPI PIN sends money out of your account; it never brings money in.",
            [
                "Do not pay any 'fee' to claim a prize or refund.",
                "Do not enter your UPI PIN for a 'collect request'.",
                "Check refunds only in the official app or website.",
            ],
        ),
        L.HI: (
            "रुकिए! पैसे या इनाम पाने के लिए कभी पैसे नहीं देने पड़ते।",
            "UPI PIN डालने से पैसे आते नहीं, आपके खाते से जाते हैं।",
            [
                "इनाम या रिफंड के लिए कोई 'फीस' न दें।",
                "'कलेक्ट रिक्वेस्ट' पर UPI PIN न डालें।",
                "रिफंड सिर्फ आधिकारिक ऐप या वेबसाइट पर जांचें।",
            ],
        ),
        L.TE: (
            "ఆగండి! డబ్బు లేదా బహుమతి పొందడానికి మీరు డబ్బు చెల్లించాల్సిన అవసరం లేదు.",
            "UPI PIN ఎంటర్ చేస్తే డబ్బు రాదు, మీ ఖాతా నుంచి వెళ్తుంది.",
            [
                "బహుమతి లేదా రీఫండ్ కోసం ఎలాంటి 'ఫీజు' చెల్లించవద్దు.",
                "'కలెక్ట్ రిక్వెస్ట్'కు UPI PIN ఎంటర్ చేయవద్దు.",
                "రీఫండ్‌ను అధికారిక యాప్ లేదా వెబ్‌సైట్‌లో మాత్రమే చూడండి.",
            ],
        ),
    },
    S.FAMILY_EMERGENCY: {
        L.EN: (
            "Verify first. Voices can be cloned.",
            "Scammers copy a relative's voice or use a 'new number' story to ask for urgent money.",
            [
                "Call your relative on their saved number.",
                "Ask a question only they can answer.",
                "Do not send money until you have spoken to them directly.",
            ],
        ),
        L.HI: (
            "पहले पुष्टि कीजिए! आवाज़ की नकल की जा सकती है।",
            "ठग रिश्तेदार की आवाज़ की नकल करते हैं या 'नया नंबर' की कहानी बनाकर जल्दी पैसे मांगते हैं।",
            [
                "अपने रिश्तेदार को उनके सेव किए हुए नंबर पर कॉल करें।",
                "ऐसा सवाल पूछें जिसका जवाब सिर्फ उन्हें पता हो।",
                "सीधे बात होने तक पैसे न भेजें।",
            ],
        ),
        L.TE: (
            "ముందు నిర్ధారించుకోండి! గొంతును అనుకరించవచ్చు.",
            "మోసగాళ్లు బంధువు గొంతును అనుకరిస్తారు లేదా 'కొత్త నంబర్' కథ చెప్పి అత్యవసరంగా డబ్బు అడుగుతారు.",
            [
                "మీ బంధువుకు వారి సేవ్ చేసిన నంబర్‌కే కాల్ చేయండి.",
                "వారికి మాత్రమే తెలిసిన ప్రశ్న అడగండి.",
                "నేరుగా మాట్లాడే వరకు డబ్బు పంపవద్దు.",
            ],
        ),
    },
}


def template(
    language: Language, scam_type: ScamType, tier: Tier, confidence: float, phase: str
) -> Intervention | None:
    """Returns the template intervention, or None for ``ALLOW``."""
    if tier is Tier.ALLOW:
        return None
    entry = _TEMPLATES.get(scam_type)
    if entry is not None and (confidence >= 0.5 or tier.rank >= Tier.FRICTION.rank):
        headline, message, steps = entry[language]
    else:
        headline, message, steps = _GENERIC[language]
    steps = list(steps)
    if tier is Tier.HOLD:
        steps.append(_HOLD_STEP[language])
    if tier.rank >= Tier.FRICTION.rank or phase == "call":
        steps.append(_HELPLINE[language])
    return Intervention(
        language=language, headline=headline, message=message, steps=steps, source="template"
    )
