# SPDX-License-Identifier: Apache-2.0
"""Synthetic conversation templates for demos, tests and evaluation.

All text is invented for this project. Scam scripts come in two families:

* ``seen``   - phrased the way the lexicon expects (in-distribution), and
* ``unseen`` - paraphrased to avoid the lexicon's cue words, to measure how the
  deterministic layer degrades on novel wording (the gap the Gemini semantic
  layer is designed to close).

Benign scripts deliberately reuse alarming vocabulary (OTP warnings, parcels,
police verification, urgent family requests) to stress false positives.
"""

from __future__ import annotations

from vigil.domain.models import ScamType

S = ScamType

# SCAMS[type][language][family] -> caller turns, in order. The final turn is
# the payment demand (or credential demand). Slots: {name} {org} {bank} {amt}.
SCAMS: dict[ScamType, dict[str, dict[str, list[str]]]] = {
    S.DIGITAL_ARREST: {
        "en": {
            "seen": [
                "This is {name} from {org}. An arrest warrant has been issued in your name in a money laundering case.",
                "Your Aadhaar was used for illegal transactions. This is a confidential matter, do not tell anyone and do not disconnect the call.",
                "To prove your innocence you must immediately transfer {amt} to the RBI safe account for verification. It will be refunded after the investigation.",
            ],
            "unseen": [
                "Good afternoon, I am calling on behalf of the {org} enforcement wing. A serious complaint has been lodged against a SIM linked to you.",
                "You are being monitored on video until the inquiry finishes. Speak to nobody, not even relatives, or the matter will worsen for you.",
                "The funds need to be moved to a government-held escrow so we can audit them. Complete it within the hour and you will get everything back.",
            ],
        },
        "hi": {
            "seen": [
                "मैं {org} से {name} बोल रहा हूँ। आपके नाम पर मनी लॉन्ड्रिंग का वारंट जारी हुआ है।",
                "यह गोपनीय मामला है, किसी को मत बताना और कॉल मत काटना। आप डिजिटल अरेस्ट में हैं।",
                "अपनी बेगुनाही साबित करने के लिए तुरंत {amt} सुरक्षित खाते में ट्रांसफर करें, जांच के बाद वापस कर दिया जाएगा।",
            ],
            "unseen": [
                "नमस्ते, मैं {org} की जांच शाखा से बोल रहा हूँ। आपके सिम से जुड़ी एक गंभीर शिकायत मिली है।",
                "जांच पूरी होने तक आप वीडियो निगरानी में रहेंगे। अपने परिवार से भी इस बारे में बात करना आपके लिए मुश्किल खड़ी करेगा।",
                "रकम को सरकारी निगरानी वाले खाते में डालना होगा ताकि हम उसकी जांच कर सकें। एक घंटे में कर दीजिए, सब लौटा दिया जाएगा।",
            ],
        },
        "hinglish": {
            "seen": [
                "Main {org} se {name} bol raha hoon. Aapke naam par arrest warrant nikla hai money laundering case mein.",
                "Yeh confidential case hai, kisi ko mat batana aur call mat kaatna. Aap digital arrest mein hain.",
                "Turant {amt} RBI ke safe account mein transfer karo verification ke liye, baad mein wapas ho jayega.",
            ],
            "unseen": [
                "Namaste, main {org} ki enquiry wing se hoon. Aapke SIM ke against ek serious complaint aayi hai.",
                "Jaanch khatam hone tak aap camera par rahenge. Kisi se bhi is baare mein baat ki to aapke liye problem badhegi.",
                "Paisa government escrow mein daalna hoga taaki hum audit kar sakein. Ek ghante mein kar dijiye, sab laut jayega.",
            ],
        },
        "te": {
            "seen": [
                "నేను {org} నుండి {name} మాట్లాడుతున్నాను. మనీ లాండరింగ్ కేసులో మీ పేరు మీద అరెస్ట్ వారెంట్ ఉంది.",
                "ఇది రహస్యం, ఎవరికీ చెప్పొద్దు, కాల్ కట్ చేయకండి. మీరు డిజిటల్ అరెస్ట్‌లో ఉన్నారు.",
                "మీ నిర్దోషిత్వం నిరూపించుకోవడానికి వెంటనే {amt} సేఫ్ అకౌంట్‌కు ట్రాన్స్‌ఫర్ చేయండి, దర్యాప్తు తర్వాత తిరిగి ఇస్తాం.",
            ],
            "unseen": [
                "నమస్కారం, నేను {org} విచారణ విభాగం నుండి మాట్లాడుతున్నాను. మీ సిమ్‌పై తీవ్రమైన ఫిర్యాదు వచ్చింది.",
                "విచారణ ముగిసే వరకు మీరు కెమెరా నిఘాలో ఉంటారు. బంధువులతో కూడా దీని గురించి మాట్లాడితే మీకే ఇబ్బంది.",
                "ఆ మొత్తాన్ని ప్రభుత్వ ఎస్క్రో ఖాతాలోకి మార్చాలి, మేము పరిశీలించడానికి. గంటలో పూర్తి చేస్తే అంతా వెనక్కి వస్తుంది.",
            ],
        },
    },
    S.KYC_OTP: {
        "en": {
            "seen": [
                "Hello sir, I am calling from {bank} customer care. Your KYC has expired and your account will be blocked today.",
                "To update it please share the OTP you just received on your phone, and install the support app I am sending.",
                "Sir please tell me the OTP immediately, otherwise your account will be suspended.",
            ],
            "unseen": [
                "Good morning, this is the compliance desk of {bank}. Our records show a mismatch in your documents, which can restrict your card.",
                "I have sent a six digit code to your number; kindly read it back to me so I can complete the re-verification on my side.",
                "Without that code the restriction goes live in a few minutes, so please be quick.",
            ],
        },
        "hi": {
            "seen": [
                "नमस्ते सर, मैं {bank} कस्टमर केयर से बोल रहा हूँ। आपका केवाईसी एक्सपायर हो गया है और आज आपका खाता ब्लॉक हो जाएगा।",
                "अपडेट के लिए आपके फोन पर जो ओटीपी आया है वो तुरंत बताइए, और मैं जो ऐप भेज रहा हूँ उसे डाउनलोड कीजिए।",
                "सर, ओटीपी बताइए वरना खाता बंद हो जाएगा।",
            ],
            "unseen": [
                "नमस्कार, मैं {bank} के अनुपालन विभाग से हूँ। आपके दस्तावेज़ों में गड़बड़ी मिली है जिससे आपका कार्ड सीमित हो सकता है।",
                "मैंने आपके नंबर पर छह अंकों का कोड भेजा है, कृपया उसे मुझे पढ़कर सुनाइए ताकि मैं दोबारा सत्यापन पूरा कर सकूँ।",
                "इस कोड के बिना कुछ ही मिनटों में पाबंदी लग जाएगी, इसलिए जल्दी कीजिए।",
            ],
        },
        "hinglish": {
            "seen": [
                "Hello sir, main {bank} customer care se bol raha hoon. Aapka KYC expire ho gaya hai aur aaj account block ho jayega.",
                "Update ke liye jo OTP aaya hai woh turant bataiye aur main jo app bhej raha hoon use download kijiye.",
                "Sir OTP bata dijiye warna account band ho jayega.",
            ],
            "unseen": [
                "Namaste, main {bank} ke compliance department se hoon. Aapke documents mein mismatch mila hai jisse card limited ho sakta hai.",
                "Maine aapke number par six digit code bheja hai, usse mujhe padh kar sunaiye taaki main re-verification complete kar sakoon.",
                "Is code ke bina kuch hi minutes mein restriction lag jayegi, to jaldi kijiye.",
            ],
        },
        "te": {
            "seen": [
                "హలో సర్, నేను {bank} కస్టమర్ కేర్ నుండి మాట్లాడుతున్నాను. మీ కేవైసీ ఎక్స్పైర్ అయింది, ఈ రోజు మీ ఖాతా బ్లాక్ అవుతుంది.",
                "అప్డేట్ కోసం మీ ఫోన్‌కు వచ్చిన ఓటీపీ చెప్పండి, నేను పంపే యాప్ డౌన్‌లోడ్ చేయండి.",
                "సర్, ఓటీపీ చెప్పండి లేకపోతే ఖాతా నిలిపివేయబడుతుంది.",
            ],
            "unseen": [
                "నమస్కారం, నేను {bank} కంప్లయన్స్ విభాగం నుండి మాట్లాడుతున్నాను. మీ పత్రాల్లో తేడా కనిపించింది, అందువల్ల మీ కార్డ్ పరిమితం కావచ్చు.",
                "మీ నంబర్‌కు ఆరు అంకెల కోడ్ పంపాను, దాన్ని నాకు చదివి వినిపించండి, నేను మళ్లీ ధృవీకరణ పూర్తి చేస్తాను.",
                "ఆ కోడ్ లేకపోతే కొన్ని నిమిషాల్లో ఆంక్షలు అమలవుతాయి, కాబట్టి త్వరగా చెప్పండి.",
            ],
        },
    },
    S.INVESTMENT: {
        "en": {
            "seen": [
                "Hi, I am an analyst from Alpha Wealth. Join our VIP trading group on Telegram.",
                "We offer guaranteed returns of 40% per month with no risk, my members have doubled their money.",
                "Transfer {amt} to this account today to lock your slot, only a few seats left.",
            ],
            "unseen": [
                "Hello, I manage a private fund for a limited set of friends and family. Last quarter our members saw their capital grow nearly threefold.",
                "There is no way to lose here because my algorithm only trades with inside knowledge from a brokerage contact.",
                "Put {amt} into the fund account today to hold your place, the window closes tonight.",
            ],
        },
        "hi": {
            "seen": [
                "नमस्ते, मैं अल्फा वेल्थ से एनालिस्ट बोल रहा हूँ। हमारे वीआईपी ट्रेडिंग टेलीग्राम ग्रुप से जुड़ें।",
                "हम पक्का मुनाफा देते हैं, महीने में 40% रिटर्न, बिना रिस्क। हमारे मेंबर्स के पैसे डबल हो चुके हैं।",
                "आज ही {amt} इस खाते में ट्रांसफर करें, सीटें सीमित हैं।",
            ],
            "unseen": [
                "नमस्ते, मैं दोस्तों और परिवार के एक सीमित समूह के लिए निजी फंड चलाता हूँ। पिछली तिमाही में हमारे सदस्यों की पूंजी लगभग तीन गुना हो गई।",
                "यहाँ नुकसान की गुंजाइश ही नहीं है क्योंकि मेरा एल्गोरिदम ब्रोकरेज के एक संपर्क से मिली अंदर की जानकारी पर ट्रेड करता है।",
                "अपनी जगह पक्की करने के लिए आज ही {amt} फंड खाते में डालिए, आज रात खिड़की बंद हो जाएगी।",
            ],
        },
        "hinglish": {
            "seen": [
                "Hi, main Alpha Wealth se analyst bol raha hoon. Hamare VIP trading Telegram group se jud jaiye.",
                "Hum guaranteed returns dete hain, mahine mein 40% bina risk. Members ke paise double ho gaye hain.",
                "Aaj hi {amt} is account mein transfer kar do, seats limited hain.",
            ],
            "unseen": [
                "Namaste, main doston aur family ke limited group ke liye private fund chalata hoon. Pichhle quarter mein members ki capital lagbhag teen guna ho gayi.",
                "Yahan loss ka chance hi nahi hai kyunki mera algorithm brokerage contact se mili andar ki jaankari par trade karta hai.",
                "Apni jagah pakki karne ke liye aaj hi {amt} fund account mein daal dijiye, aaj raat window band ho jayegi.",
            ],
        },
        "te": {
            "seen": [
                "హాయ్, నేను ఆల్ఫా వెల్త్ నుండి అనలిస్ట్‌ని. మా వీఐపీ ట్రేడింగ్ టెలిగ్రామ్ గ్రూప్‌లో చేరండి.",
                "మేము గ్యారెంటీ లాభం ఇస్తాం, నెలకు 40% రిటర్న్స్, రిస్క్ లేకుండా. మా సభ్యుల డబ్బు రెట్టింపు అయింది.",
                "ఈ రోజే {amt} ఈ ఖాతాకు ట్రాన్స్‌ఫర్ చేయండి, సీట్లు పరిమితం.",
            ],
            "unseen": [
                "నమస్కారం, స్నేహితులు కుటుంబ సభ్యుల పరిమిత సమూహం కోసం నేను ప్రైవేట్ ఫండ్ నడుపుతున్నాను. గత త్రైమాసికంలో సభ్యుల మూలధనం దాదాపు మూడు రెట్లు పెరిగింది.",
                "ఇక్కడ నష్టం వచ్చే అవకాశమే లేదు ఎందుకంటే నా అల్గారిథం బ్రోకరేజ్ పరిచయం ఇచ్చే లోపలి సమాచారంతో ట్రేడ్ చేస్తుంది.",
                "మీ స్థానం ఖాయం చేసుకోవడానికి ఈ రోజే {amt} ఫండ్ ఖాతాలో వేయండి, ఈ రాత్రితో అవకాశం ముగుస్తుంది.",
            ],
        },
    },
    S.COURIER_CUSTOMS: {
        "en": {
            "seen": [
                "This is {name} from FedEx. A parcel in your name has been seized at customs, it contains drugs and fake passports.",
                "Your Aadhaar is linked to this illegal parcel. I am connecting you to the Narcotics Bureau officer, do not disconnect the call.",
                "The officer says to clear the case you must pay {amt} immediately to the verification account.",
            ],
            "unseen": [
                "Hello, I'm with the international shipping desk. A box shipped under your ID was flagged by inspectors for prohibited contents.",
                "I will forward you to a senior investigator now. Please remain with us and keep this between us while it is reviewed.",
                "To release the box and close the file you need to deposit {amt} today into the account he gives you.",
            ],
        },
        "hi": {
            "seen": [
                "मैं फेडेक्स से {name} बोल रहा हूँ। आपके नाम का पार्सल कस्टम में पकड़ा गया है, उसमें ड्रग्स और नकली पासपोर्ट हैं।",
                "आपका आधार इस गैरकानूनी पार्सल से लिंक है। मैं आपको नारकोटिक्स अधिकारी से जोड़ रहा हूँ, कॉल मत काटना।",
                "अधिकारी कह रहे हैं कि केस खत्म करने के लिए तुरंत {amt} वेरिफिकेशन खाते में ट्रांसफर कीजिए।",
            ],
            "unseen": [
                "नमस्ते, मैं अंतरराष्ट्रीय शिपिंग डेस्क से बोल रहा हूँ। आपकी आईडी पर भेजे गए एक डिब्बे को निरीक्षकों ने प्रतिबंधित सामग्री के लिए रोका है।",
                "मैं आपको अभी एक वरिष्ठ जांचकर्ता से मिला रहा हूँ। समीक्षा पूरी होने तक लाइन पर बने रहिए और इसे अपने तक ही रखिए।",
                "डिब्बा छुड़ाने और फाइल बंद करने के लिए आज ही {amt} उस खाते में जमा करवाइए जो वे बताएंगे।",
            ],
        },
        "hinglish": {
            "seen": [
                "Main {name} bol raha hoon FedEx se. Aapke naam ka parcel customs mein pakda gaya hai, usme drugs aur fake passport hain.",
                "Aapka aadhaar link hai is illegal parcel se. Main aapko Narcotics officer se connect kar raha hoon, call mat kaatna.",
                "Officer keh rahe hain case khatam karne ke liye turant {amt} verification account mein transfer karo.",
            ],
            "unseen": [
                "Namaste, main international shipping desk se hoon. Aapki ID par bheje gaye ek box ko inspectors ne prohibited contents ke liye roka hai.",
                "Main aapko abhi ek senior investigator se milata hoon. Review hone tak line par rahiye aur ise apne tak hi rakhiye.",
                "Box chhudane aur file band karne ke liye aaj hi {amt} us account mein jama karwa dijiye jo woh batayenge.",
            ],
        },
        "te": {
            "seen": [
                "నేను ఫెడెక్స్ నుండి {name} మాట్లాడుతున్నాను. మీ పేరు మీద పార్సిల్ కస్టమ్స్‌లో సీజ్ అయింది, అందులో డ్రగ్స్, నకిలీ పాస్‌పోర్టులు ఉన్నాయి.",
                "మీ ఆధార్ ఈ అక్రమ పార్సిల్‌తో లింక్ అయింది. నార్కోటిక్స్ అధికారికి కనెక్ట్ చేస్తున్నాను, కాల్ కట్ చేయకండి.",
                "కేసు ముగించాలంటే వెంటనే {amt} వెరిఫికేషన్ ఖాతాకు ట్రాన్స్‌ఫర్ చేయండి అని అధికారి చెబుతున్నారు.",
            ],
            "unseen": [
                "నమస్కారం, నేను అంతర్జాతీయ షిప్పింగ్ డెస్క్ నుండి మాట్లాడుతున్నాను. మీ ఐడీపై పంపిన ఒక పెట్టెను తనిఖీదారులు నిషేధిత వస్తువుల కోసం ఆపారు.",
                "ఇప్పుడు మిమ్మల్ని ఒక సీనియర్ దర్యాప్తు అధికారితో కలుపుతాను. సమీక్ష పూర్తయ్యే వరకు లైన్‌లో ఉండండి, ఇది మన మధ్యే ఉంచండి.",
                "పెట్టె విడిపించడానికి, ఫైల్ మూసివేయడానికి ఈ రోజే {amt} ఆయన చెప్పే ఖాతాలో జమ చేయండి.",
            ],
        },
    },
    S.PRIZE_REFUND: {
        "en": {
            "seen": [
                "Congratulations! You have won a lucky draw prize of ₹25 lakh from Reliance Jio.",
                "To claim your prize pay the processing fee of {amt} first.",
                "Now enter your UPI PIN to receive the money into your account.",
            ],
            "unseen": [
                "Great news, your mobile number was picked in our anniversary giveaway and you are entitled to a large cash award.",
                "Before we can release it there is a small handling charge of {amt} that has to come from you.",
                "Approve the request that appears on your payment app and key in your secret code so the award lands in your account.",
            ],
        },
        "hi": {
            "seen": [
                "बधाई हो! आपने रिलायंस जियो का 25 लाख का लकी ड्रा इनाम जीता है।",
                "इनाम पाने के लिए पहले {amt} प्रोसेसिंग फीस जमा कीजिए।",
                "अब पैसे पाने के लिए अपना यूपीआई पिन डालिए।",
            ],
            "unseen": [
                "खुशखबरी, हमारे वार्षिकोत्सव ड्रॉ में आपका मोबाइल नंबर चुना गया है और आप एक बड़ी नकद राशि के हकदार हैं।",
                "इसे जारी करने से पहले {amt} का छोटा सा हैंडलिंग शुल्क आपको देना होगा।",
                "आपके पेमेंट ऐप पर जो अनुरोध आए उसे मंज़ूर करें और अपना गुप्त कोड डालें ताकि राशि खाते में पहुँचे।",
            ],
        },
        "hinglish": {
            "seen": [
                "Badhai ho! Aapne Reliance Jio ka 25 lakh ka lucky draw jeeta hai.",
                "Inaam lene ke liye pehle {amt} processing fee jama kijiye.",
                "Ab paise pane ke liye apna UPI PIN daliye.",
            ],
            "unseen": [
                "Khushkhabri, humare anniversary giveaway mein aapka mobile number chuna gaya hai aur aap badi cash raashi ke hakdaar hain.",
                "Ise release karne se pehle {amt} ka chhota sa handling charge aapko dena hoga.",
                "Aapke payment app par jo request aaye use approve kijiye aur apna secret code daliye taaki raashi account mein pahunche.",
            ],
        },
        "te": {
            "seen": [
                "అభినందనలు! మీరు రిలయన్స్ జియో 25 లక్షల లక్కీ డ్రా బహుమతి గెలుచుకున్నారు.",
                "బహుమతి పొందడానికి ముందు {amt} ప్రాసెసింగ్ ఫీజు చెల్లించండి.",
                "ఇప్పుడు డబ్బు పొందాలంటే మీ యూపీఐ పిన్ ఎంటర్ చేయండి.",
            ],
            "unseen": [
                "శుభవార్త, మా వార్షికోత్సవ డ్రాలో మీ మొబైల్ నంబర్ ఎంపికైంది, మీరు పెద్ద నగదు మొత్తానికి అర్హులు.",
                "దాన్ని విడుదల చేయడానికి ముందు మీరు {amt} చిన్న హ్యాండ్లింగ్ ఛార్జ్ చెల్లించాలి.",
                "మీ పేమెంట్ యాప్‌లో వచ్చిన అభ్యర్థనను అంగీకరించి మీ రహస్య కోడ్ ఇవ్వండి, అప్పుడు మొత్తం ఖాతాలో పడుతుంది.",
            ],
        },
    },
    S.FAMILY_EMERGENCY: {
        "en": {
            "seen": [
                "Papa, it's me. I'm in trouble, I had an accident and I'm at the hospital. My phone is broken, this is my new number.",
                "Please don't tell mummy, she will panic. I need money urgently for the hospital bill.",
                "Send {amt} right now to this account, I will explain later.",
            ],
            "unseen": [
                "Hi uncle, it's your nephew. Something happened tonight and I am really stuck, I'm calling from a friend's phone.",
                "Keep this between us for now please, I'll sort it out with everyone later. I just need some cash quickly.",
                "Could you put {amt} into this account as fast as you can? I'll pay you back this week.",
            ],
        },
        "hi": {
            "seen": [
                "पापा, मैं बोल रहा हूँ। मैं मुसीबत में हूँ, एक्सीडेंट हो गया है और मैं हॉस्पिटल में हूँ। मेरा फोन टूट गया है, यह मेरा नया नंबर है।",
                "मम्मी को मत बताना, वो घबरा जाएंगी। मुझे अस्पताल के बिल के लिए तुरंत पैसे चाहिए।",
                "अभी इस खाते में {amt} भेज दो, मैं बाद में समझाऊँगा।",
            ],
            "unseen": [
                "हेलो चाचा जी, मैं आपका भतीजा हूँ। आज रात कुछ हो गया है और मैं सच में फंस गया हूँ, किसी दोस्त के फोन से बात कर रहा हूँ।",
                "अभी यह बात हमारे बीच ही रखिए, मैं बाद में सबको संभाल लूँगा। बस जल्दी से कुछ नकद चाहिए।",
                "क्या आप इस खाते में जितनी जल्दी हो सके {amt} डाल सकते हैं? मैं इसी हफ्ते लौटा दूँगा।",
            ],
        },
        "hinglish": {
            "seen": [
                "Papa, main bol raha hoon. Main trouble mein hoon, accident ho gaya hai aur hospital mein hoon. Phone toot gaya hai, yeh naya number hai.",
                "Mummy ko mat batana, woh ghabra jayengi. Mujhe hospital bill ke liye turant paise chahiye.",
                "Abhi is account mein {amt} bhej do, baad mein samjhaunga.",
            ],
            "unseen": [
                "Hello chacha ji, main aapka bhatija hoon. Aaj raat kuch ho gaya hai aur main sach mein phans gaya hoon, kisi dost ke phone se baat kar raha hoon.",
                "Abhi yeh baat humare beech hi rakhiye, main baad mein sabko sambhal lunga. Bas jaldi se kuch cash chahiye.",
                "Kya aap is account mein jitni jaldi ho sake {amt} daal sakte hain? Main isi hafte laut dunga.",
            ],
        },
        "te": {
            "seen": [
                "నాన్న, నేనే మాట్లాడుతున్నాను. నేను ఇబ్బందిలో ఉన్నాను, యాక్సిడెంట్ అయింది, హాస్పిటల్‌లో ఉన్నాను. ఫోన్ పగిలిపోయింది, ఇది నా కొత్త నంబర్.",
                "అమ్మకు చెప్పొద్దు, ఆమె కంగారు పడుతుంది. హాస్పిటల్ బిల్లు కోసం అత్యవసరంగా డబ్బు కావాలి.",
                "ఇప్పుడే ఈ ఖాతాకు {amt} పంపండి, తర్వాత వివరిస్తాను.",
            ],
            "unseen": [
                "హలో బాబాయ్, నేను నీ మేనల్లుడిని. ఈ రాత్రి ఏదో జరిగింది, నేను నిజంగా చిక్కుకున్నాను, స్నేహితుడి ఫోన్ నుండి మాట్లాడుతున్నాను.",
                "ప్రస్తుతానికి ఇది మనిద్దరి మధ్యే ఉంచండి, తర్వాత అందరితో సర్దుకుంటాను. త్వరగా కొంత నగదు కావాలి.",
                "మీరు వీలైనంత త్వరగా ఈ ఖాతాలో {amt} వేయగలరా? ఈ వారమే తిరిగి ఇచ్చేస్తాను.",
            ],
        },
    },
    S.REMOTE_ACCESS: {
        "en": {
            "seen": [
                "Hello, I am from the tech support team of your bank. We detected suspicious activity on your account.",
                "Please install the AnyDesk app from the link I am sending and share your screen so I can fix it.",
                "Now open your banking app and transfer {amt} to the secure account while I secure your device.",
            ],
            "unseen": [
                "Hi, I'm calling from the service desk. Your handset has been compromised and I can repair it remotely.",
                "Open the store, get the small utility I name, and give me the nine digit number it shows, then I will take it from there.",
                "Keep your banking app open and move {amt} where I tell you; this keeps it safe from the intruders.",
            ],
        },
        "hi": {
            "seen": [
                "नमस्ते, मैं आपके बैंक की टेक सपोर्ट टीम से बोल रहा हूँ। आपके खाते में संदिग्ध गतिविधि मिली है।",
                "मैं जो लिंक भेज रहा हूँ उससे एनीडेस्क ऐप डाउनलोड कीजिए और स्क्रीन शेयर कीजिए ताकि मैं ठीक कर सकूँ।",
                "अब बैंकिंग ऐप खोलिए और {amt} सुरक्षित खाते में ट्रांसफर कीजिए, मैं आपका फोन सुरक्षित कर रहा हूँ।",
            ],
            "unseen": [
                "नमस्ते, मैं सर्विस डेस्क से बोल रहा हूँ। आपके हैंडसेट में घुसपैठ हुई है और मैं उसे दूर से ठीक कर सकता हूँ।",
                "स्टोर खोलिए, मैं जिस छोटी सी यूटिलिटी का नाम बताऊँ उसे लीजिए, और जो नौ अंकों का नंबर दिखे वह मुझे दीजिए।",
                "बैंकिंग ऐप खुला रखिए और {amt} वहाँ डालिए जहाँ मैं बताऊँ; इससे घुसपैठियों से सुरक्षित रहेगा।",
            ],
        },
        "hinglish": {
            "seen": [
                "Hello, main aapke bank ki tech support team se bol raha hoon. Aapke account mein suspicious activity mili hai.",
                "Main jo link bhej raha hoon usse AnyDesk app download kijiye aur screen share kijiye taaki main fix kar sakoon.",
                "Ab banking app kholiye aur {amt} secure account mein transfer kijiye, main aapka phone secure kar raha hoon.",
            ],
            "unseen": [
                "Hi, main service desk se bol raha hoon. Aapke handset mein intrusion hua hai aur main use remotely repair kar sakta hoon.",
                "Store kholiye, main jis chhoti utility ka naam bataun use lijiye, aur jo nau digit ka number dikhe woh mujhe dijiye.",
                "Banking app khula rakhiye aur {amt} wahan daliye jahan main bataun; isse intruders se safe rahega.",
            ],
        },
        "te": {
            "seen": [
                "నమస్కారం, నేను మీ బ్యాంక్ టెక్ సపోర్ట్ టీమ్ నుండి మాట్లాడుతున్నాను. మీ ఖాతాలో అనుమానాస్పద కార్యకలాపం కనిపించింది.",
                "నేను పంపే లింక్ నుండి ఎనీడెస్క్ యాప్ డౌన్‌లోడ్ చేసి స్క్రీన్ షేర్ చేయండి, నేను సరిచేస్తాను.",
                "ఇప్పుడు బ్యాంకింగ్ యాప్ తెరిచి {amt} సురక్షిత ఖాతాకు ట్రాన్స్‌ఫర్ చేయండి, నేను మీ ఫోన్‌ను సురక్షితం చేస్తున్నాను.",
            ],
            "unseen": [
                "హలో, నేను సర్వీస్ డెస్క్ నుండి మాట్లాడుతున్నాను. మీ హ్యాండ్‌సెట్‌లోకి చొరబడ్డారు, నేను దూరం నుండి బాగు చేయగలను.",
                "స్టోర్ తెరిచి నేను చెప్పే చిన్న యుటిలిటీ తీసుకోండి, అది చూపే తొమ్మిది అంకెల నంబర్ నాకు ఇవ్వండి.",
                "బ్యాంకింగ్ యాప్ తెరిచే ఉంచి, నేను చెప్పిన చోట {amt} వేయండి; దీంతో చొరబాటుదారుల నుండి సురక్షితంగా ఉంటుంది.",
            ],
        },
    },
}

# BENIGN[kind][language] -> list of (speaker, text). Speakers: "caller", "user", "system".
BENIGN: dict[str, dict[str, list[tuple[str, str]]]] = {
    "bank_advisory": {
        "en": [
            (
                "system",
                "Dear customer, this is an automated message from your bank. Never share your OTP, PIN or CVV with anyone, even if they claim to be bank staff.",
            )
        ],
        "hinglish": [
            (
                "system",
                "Pyare grahak, yeh aapke bank ka automated message hai. Apna OTP, PIN ya CVV kisi ko na batayein, chahe woh bank staff hone ka daava kare.",
            )
        ],
        "hi": [
            (
                "system",
                "प्रिय ग्राहक, यह आपके बैंक का स्वचालित संदेश है। अपना ओटीपी, पिन या सीवीवी किसी को न बताएं, चाहे वह बैंक कर्मचारी होने का दावा करे।",
            )
        ],
        "te": [
            (
                "system",
                "ప్రియమైన కస్టమర్, ఇది మీ బ్యాంక్ నుండి ఆటోమేటెడ్ సందేశం. మీ ఓటీపీ, పిన్ లేదా సీవీవీని ఎవరికీ చెప్పవద్దు, బ్యాంక్ సిబ్బంది అని చెప్పినా సరే.",
            )
        ],
    },
    "delivery_cod": {
        "en": [
            (
                "caller",
                "Hello, I'm the delivery agent. Your parcel has arrived at your gate. The cash on delivery amount is {amt}, you can pay by UPI on the merchant QR.",
            ),
            ("user", "Okay, I'm coming down now."),
        ],
        "hinglish": [
            (
                "caller",
                "Hello, main delivery agent bol raha hoon. Aapka parcel gate par aa gaya hai. COD amount {amt} hai, merchant QR par UPI se pay kar sakte hain.",
            ),
            ("user", "Theek hai, main abhi neeche aa raha hoon."),
        ],
        "hi": [
            (
                "caller",
                "नमस्ते, मैं डिलीवरी एजेंट हूँ। आपका पार्सल गेट पर पहुँच गया है। कैश ऑन डिलीवरी की रकम {amt} है, आप मर्चेंट क्यूआर पर यूपीआई से भुगतान कर सकते हैं।",
            ),
            ("user", "ठीक है, मैं अभी नीचे आ रहा हूँ।"),
        ],
        "te": [
            (
                "caller",
                "హలో, నేను డెలివరీ ఏజెంట్‌ను. మీ పార్సిల్ గేట్ దగ్గరకు వచ్చింది. క్యాష్ ఆన్ డెలివరీ మొత్తం {amt}, మర్చంట్ క్యూఆర్‌పై యూపీఐ ద్వారా చెల్లించవచ్చు.",
            ),
            ("user", "సరే, నేను ఇప్పుడే కిందకి వస్తున్నాను."),
        ],
    },
    "friend_split": {
        "en": [
            ("caller", "Hey, dinner came to {amt} in total, can you send your share?"),
            ("user", "Sure, sending it now."),
        ],
        "hinglish": [
            ("caller", "Arre, dinner ka total {amt} aaya, apna share bhej dega?"),
            ("user", "Haan bhai, abhi bhejta hoon."),
        ],
        "hi": [
            ("caller", "अरे, डिनर का कुल {amt} आया, अपना हिस्सा भेज दोगे?"),
            ("user", "हाँ यार, अभी भेजता हूँ।"),
        ],
        "te": [
            ("caller", "హేయ్, డిన్నర్ మొత్తం {amt} అయింది, నీ వాటా పంపిస్తావా?"),
            ("user", "సరే రా, ఇప్పుడే పంపుతాను."),
        ],
    },
    "landlord_rent": {
        "en": [
            (
                "caller",
                "Hello, this is your new landlord. Rent for this month is {amt}, please pay by the 5th. I'll send my account details on WhatsApp.",
            ),
            ("user", "Okay, I'll transfer it tomorrow morning."),
        ],
        "hinglish": [
            (
                "caller",
                "Hello, main aapka naya landlord hoon. Is mahine ka rent {amt} hai, 5 tareekh tak pay kar dijiye. Account details WhatsApp par bhejta hoon.",
            ),
            ("user", "Theek hai, kal subah transfer kar dunga."),
        ],
        "hi": [
            (
                "caller",
                "नमस्ते, मैं आपका नया मकान मालिक हूँ। इस महीने का किराया {amt} है, कृपया 5 तारीख तक दे दीजिए। खाते की जानकारी व्हाट्सएप पर भेजता हूँ।",
            ),
            ("user", "ठीक है, कल सुबह भेज दूँगा।"),
        ],
        "te": [
            (
                "caller",
                "నమస్కారం, నేను మీ కొత్త ఇంటి యజమానిని. ఈ నెల అద్దె {amt}, 5వ తేదీలోపు చెల్లించండి. ఖాతా వివరాలు వాట్సాప్‌లో పంపుతాను.",
            ),
            ("user", "సరే, రేపు ఉదయం పంపుతాను."),
        ],
    },
    "family_real": {
        "en": [
            (
                "caller",
                "Beta, your grandmother was admitted to the hospital this morning. Can you send {amt} for the bill? I'm at the hospital now.",
            ),
            ("user", "Of course, I'll send it right away. Is she okay?"),
        ],
        "hinglish": [
            (
                "caller",
                "Beta, dadi ko aaj subah hospital mein admit karaya hai. Bill ke liye {amt} bhej sakte ho? Main abhi hospital mein hoon.",
            ),
            ("user", "Haan papa, abhi bhejta hoon. Dadi theek hain na?"),
        ],
        "hi": [
            (
                "caller",
                "बेटा, दादी को आज सुबह अस्पताल में भर्ती कराया है। बिल के लिए {amt} भेज सकते हो? मैं अभी अस्पताल में हूँ।",
            ),
            ("user", "हाँ पापा, अभी भेजता हूँ। दादी ठीक हैं ना?"),
        ],
        "te": [
            (
                "caller",
                "బాబు, అమ్మమ్మను ఈ ఉదయం ఆసుపత్రిలో చేర్చాం. బిల్లు కోసం {amt} పంపగలవా? నేను ఇప్పుడు ఆసుపత్రిలోనే ఉన్నాను.",
            ),
            ("user", "సరే నాన్న, ఇప్పుడే పంపుతాను. అమ్మమ్మ బాగానే ఉందా?"),
        ],
    },
    "used_car": {
        "en": [
            (
                "caller",
                "I can give you the car for {amt}. Please transfer to my account and I'll hand over the keys and papers.",
            ),
            ("user", "Fine, I'll transfer it while we are on the call."),
        ],
        "hinglish": [
            (
                "caller",
                "Gaadi main aapko {amt} mein de dunga. Mere account mein transfer kar dijiye, main chabi aur papers de dunga.",
            ),
            ("user", "Theek hai, call par hi transfer kar deta hoon."),
        ],
        "hi": [
            (
                "caller",
                "गाड़ी मैं आपको {amt} में दे दूँगा। मेरे खाते में ट्रांसफर कर दीजिए, मैं चाबी और कागज़ात दे दूँगा।",
            ),
            ("user", "ठीक है, कॉल पर ही ट्रांसफर कर देता हूँ।"),
        ],
        "te": [
            ("caller", "కారు మీకు {amt}కి ఇస్తాను. నా ఖాతాకు ట్రాన్స్‌ఫర్ చేయండి, తాళాలు, పత్రాలు ఇస్తాను."),
            ("user", "సరే, కాల్‌లోనే ట్రాన్స్‌ఫర్ చేస్తాను."),
        ],
    },
    "bank_care_genuine": {
        "en": [
            (
                "caller",
                "Thank you for calling HDFC Bank customer care. I have blocked your lost card as requested. A new card will arrive in seven days. For your safety, never share the OTP or PIN with anyone.",
            ),
            ("user", "Thank you, that's all I needed."),
        ],
    },
    "advisor_sip": {
        "en": [
            (
                "caller",
                "Based on your goals I suggest a monthly SIP of {amt} in an index fund. Returns are market-linked, and no one can promise guaranteed returns.",
            ),
            ("user", "That sounds reasonable, I'll think about it."),
        ],
    },
    "police_verification": {
        "en": [
            (
                "caller",
                "This is the passport verification officer from the local police. Please visit the nearest police station tomorrow with your original documents.",
            ),
            ("user", "Okay, what time should I come?"),
        ],
    },
    "insurance_premium": {
        "en": [
            (
                "system",
                "Your insurance premium of {amt} is due on the 20th. Please pay through the official app or website.",
            )
        ],
    },
}

BENIGN_WEIGHTS = {
    "bank_advisory": 1.0,
    "delivery_cod": 1.0,
    "friend_split": 1.5,
    "landlord_rent": 1.0,
    "family_real": 0.8,
    "used_car": 0.8,
    "bank_care_genuine": 0.6,
    "advisor_sip": 0.6,
    "police_verification": 0.6,
    "insurance_premium": 0.8,
}

FILLER_USER = {
    "en": ["Hello?", "Who is this?", "What do you mean?", "I don't understand.", "Please explain."],
    "hinglish": ["Hello?", "Aap kaun?", "Matlab kya?", "Samajh nahi aaya.", "Thoda samjhaiye."],
    "hi": ["हेलो?", "आप कौन?", "इसका मतलब?", "मुझे समझ नहीं आया।", "ज़रा समझाइए।"],
    "te": ["హలో?", "మీరు ఎవరు?", "అంటే ఏమిటి?", "నాకు అర్థం కాలేదు.", "కొంచెం వివరించండి."],
}

NAMES = [
    "Inspector Verma",
    "Officer Rao",
    "Sub-Inspector Khan",
    "Mr. Sharma",
    "Officer Reddy",
    "Agent Singh",
]
ORGS = [
    "Mumbai Police Cyber Crime",
    "Delhi Police",
    "CBI",
    "Customs Department",
    "Narcotics Control Bureau",
    "TRAI",
]
BANKS = ["SBI", "HDFC Bank", "ICICI Bank", "Axis Bank", "Kotak Bank", "PNB"]
