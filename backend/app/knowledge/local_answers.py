"""Offline assistant answers in Indian languages.

When there is no LLM, the assistant composes answers from the person's own
matches using these templates. The question's language is taken from its
script (Bengali, Telugu, Tamil, Devanagari); Marathi and Hindi share
Devanagari, so the app's language and a few Marathi words decide between them.
Scheme names, amounts and links stay as the dataset has them.
"""
from __future__ import annotations

import re
from datetime import date

SCRIPTS = [
    ("bn", re.compile(r"[ঀ-৿]")),
    ("te", re.compile(r"[ఀ-౿]")),
    ("ta", re.compile(r"[஀-௿]")),
]
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
MARATHI_WORDS = ("आहे", "आहेत", "मला", "मी ", "कोणत्या", "कोणती", "कोणते", "साठी", "आणि", "काय", "करू", "पाहिजे", "शेवटची", "कागदपत्रे", "किती")

LANGS = ("hi", "mr", "bn", "te", "ta")


def question_lang(question: str, hint: str | None = None) -> str:
    """'hi', 'mr', 'bn', 'te', 'ta' or 'en'."""
    q = question or ""
    for code, rx in SCRIPTS:
        if rx.search(q):
            return code
    if DEVANAGARI.search(q):
        if hint == "mr" or any(w in q for w in MARATHI_WORDS):
            return "mr"
        return "hi"
    return "en"


# What each kind of question looks like in each language
KEYWORDS: dict[str, dict[str, tuple[str, ...]]] = {
    "hi": {
        "eligibility": ("पात्र", "योग्य", "कौन सी योजना", "कौनसी योजना", "कौन सी स्कॉलरशिप", "मिल सकती", "मिल सकता"),
        "documents": ("दस्तावेज", "कागज", "डॉक्यूमेंट", "प्रमाण पत्र", "प्रमाणपत्र"),
        "deadlines": ("तारीख", "तिथि", "आखिरी", "अंतिम", "कब तक", "डेडलाइन"),
        "benefits": ("राशि", "पैसे", "कितना", "कितने", "रुपये", "फायदा"),
        "how_to_apply": ("आवेदन कैसे", "कैसे अप्लाई", "कहाँ आवेदन", "कहां आवेदन", "आवेदन करें"),
        "jobs": ("नौकरी", "जॉब", "करियर"),
    },
    "mr": {
        "eligibility": ("पात्र", "कोणत्या योजना", "कोणती योजना", "कोणत्या योजनांसाठी", "मिळू शकते", "मिळेल", "शिष्यवृत्ती"),
        "documents": ("कागदपत्र", "दस्तऐवज", "प्रमाणपत्र", "डॉक्युमेंट"),
        "deadlines": ("शेवटची तारीख", "तारीख", "मुदत", "कधीपर्यंत", "अंतिम"),
        "benefits": ("किती", "रक्कम", "पैसे", "रुपये", "फायदा"),
        "how_to_apply": ("अर्ज कसा", "अर्ज कुठे", "कसा करायचा", "अर्ज करू"),
        "jobs": ("नोकरी", "जॉब", "करिअर"),
    },
    "bn": {
        "eligibility": ("যোগ্য", "কোন প্রকল্প", "কোন বৃত্তি", "পেতে পারি", "পাব", "বৃত্তি"),
        "documents": ("নথি", "কাগজ", "ডকুমেন্ট", "সার্টিফিকেট", "প্রমাণপত্র", "শংসাপত্র"),
        "deadlines": ("শেষ তারিখ", "তারিখ", "কবে", "কত দিন", "সময়সীমা", "ডেডলাইন"),
        "benefits": ("কত টাকা", "টাকা", "পরিমাণ", "সুবিধা", "কত"),
        "how_to_apply": ("আবেদন কীভাবে", "কিভাবে আবেদন", "কীভাবে আবেদন", "কোথায় আবেদন", "আবেদন করব"),
        "jobs": ("চাকরি", "জব", "কর্মসংস্থান", "কেরিয়ার"),
    },
    "te": {
        "eligibility": ("అర్హత", "అర్హుడ", "అర్హురాల", "ఏ పథకాలు", "ఏ స్కాలర్‌షిప్", "స్కాలర్‌షిప్", "పొందగలను"),
        "documents": ("పత్రాలు", "డాక్యుమెంట్", "సర్టిఫికెట్", "ధృవపత్రం", "కాగితాలు"),
        "deadlines": ("చివరి తేదీ", "తేదీ", "ఎప్పటి వరకు", "గడువు", "డెడ్‌లైన్"),
        "benefits": ("ఎంత", "డబ్బు", "మొత్తం", "రూపాయలు", "ప్రయోజనం"),
        "how_to_apply": ("ఎలా దరఖాస్తు", "దరఖాస్తు ఎలా", "ఎక్కడ దరఖాస్తు", "అప్లై"),
        "jobs": ("ఉద్యోగ", "జాబ్", "కెరీర్"),
    },
    "ta": {
        "eligibility": ("தகுதி", "எந்த திட்ட", "எந்தத் திட்ட", "உதவித்தொகை", "கிடைக்கும்", "பெற முடியும்"),
        "documents": ("ஆவண", "சான்றிதழ்", "டாக்குமென்ட்", "காகித"),
        "deadlines": ("கடைசி தேதி", "தேதி", "எப்போது வரை", "காலக்கெடு", "கெடு"),
        "benefits": ("எவ்வளவு", "பணம்", "தொகை", "ரூபாய்", "பலன்"),
        "how_to_apply": ("எப்படி விண்ணப்ப", "விண்ணப்பிப்பது எப்படி", "எங்கே விண்ணப்ப", "விண்ணப்பிக்க"),
        "jobs": ("வேலை", "ஜாப்", "தொழில்"),
    },
}

# Answer templates. {title}, {n}, {date}, {d}, {url}, {amount}, {name} are filled in.
T: dict[str, dict[str, str]] = {
    "hi": {
        "elig_none": "अभी आप किसी योजना के लिए पूरी तरह पात्र नहीं हैं। **Schemes** में देखें कि हर योजना के लिए क्या कमी है।",
        "elig_head1": "आप **1 योजना** के लिए पात्र हैं:", "elig_head": "आप **{n} योजनाओं** के लिए पात्र हैं:",
        "amount_unknown": "राशि नहीं बताई गई", "varies": "अलग-अलग",
        "dl_unknown": "अंतिम तिथि: पोर्टल देखें", "dl_left": "अंतिम तिथि {date} ({d} दिन बाकी)", "dl_closed": "{date} को बंद हो गई",
        "next_apply": "**अगला कदम:** सबसे पहले {title} के लिए आवेदन करें", "next_apply_url": "**अगला कदम:** सबसे पहले {title} के लिए आवेदन करें: {url}",
        "docs_none": "अभी कोई दस्तावेज़ तैयार करने की ज़रूरत नहीं: आप किसी योजना के लिए पूरी तरह पात्र नहीं हैं।",
        "docs_head": "जिन योजनाओं के लिए आप पात्र हैं, उनके दस्तावेज़:", "docs_count": "({n} योजनाओं के लिए)",
        "docs_next": "**अगला कदम:** **Documents** में हर दस्तावेज़ पर निशान लगाएँ या उसकी फ़ोटो स्कैन करें।",
        "dls_none": "आपकी पात्र योजनाओं में अभी कोई तय अंतिम तिथि नहीं है। तारीख़ के लिए हर पोर्टल देखें।",
        "dls_head": "आपकी पात्र योजनाओं की अगली अंतिम तिथियाँ:", "dls_line": "{date} ({d} दिन बाकी)",
        "dls_next": "**अगला कदम:** पहले {title} पूरा करें।",
        "ben_head": "आपकी {n} पात्र योजनाओं से मिलने वाली राशि:",
        "apply": "ज़्यादातर छात्रवृत्तियों के लिए **राष्ट्रीय छात्रवृत्ति पोर्टल** (https://scholarships.gov.in/) पर ऑनलाइन आवेदन होता है: मोबाइल नंबर से रजिस्टर करें, फ़ॉर्म भरें, दस्तावेज़ अपलोड करें, फिर आपका कॉलेज उसे सत्यापित करता है।",
        "jobs": "नौकरियों के लिए **Jobs** पेज खोलें: अपना रिज़्यूमे जोड़ें, हर नौकरी का फ़िट स्कोर और सीखने के लिए अगला कौशल देखें।",
        "hello": "नमस्ते{name}! मैं आपकी पात्र योजनाओं ({n}), ज़रूरी दस्तावेज़ों, अंतिम तिथियों और आवेदन के तरीके के बारे में बता सकता हूँ। पूछें: **मैं किन योजनाओं के लिए पात्र हूँ?**",
    },
    "mr": {
        "elig_none": "सध्या तुम्ही कोणत्याही योजनेसाठी पूर्णपणे पात्र नाही. प्रत्येक योजनेसाठी काय कमी आहे ते **Schemes** मध्ये पाहा.",
        "elig_head1": "तुम्ही **1 योजनेसाठी** पात्र आहात:", "elig_head": "तुम्ही **{n} योजनांसाठी** पात्र आहात:",
        "amount_unknown": "रक्कम दिलेली नाही", "varies": "वेगवेगळी",
        "dl_unknown": "शेवटची तारीख: पोर्टल पाहा", "dl_left": "शेवटची तारीख {date} ({d} दिवस बाकी)", "dl_closed": "{date} रोजी बंद झाली",
        "next_apply": "**पुढचे पाऊल:** आधी {title} साठी अर्ज करा", "next_apply_url": "**पुढचे पाऊल:** आधी {title} साठी अर्ज करा: {url}",
        "docs_none": "सध्या कोणतीही कागदपत्रे तयार करण्याची गरज नाही: तुम्ही कोणत्याही योजनेसाठी पूर्णपणे पात्र नाही.",
        "docs_head": "तुम्ही पात्र असलेल्या योजनांसाठी लागणारी कागदपत्रे:", "docs_count": "({n} योजनांसाठी)",
        "docs_next": "**पुढचे पाऊल:** **Documents** मध्ये प्रत्येक कागदपत्रावर खूण करा किंवा त्याचा फोटो स्कॅन करा.",
        "dls_none": "तुमच्या पात्र योजनांना सध्या ठरलेली शेवटची तारीख नाही. तारखेसाठी प्रत्येक पोर्टल पाहा.",
        "dls_head": "तुमच्या पात्र योजनांच्या पुढील शेवटच्या तारखा:", "dls_line": "{date} ({d} दिवस बाकी)",
        "dls_next": "**पुढचे पाऊल:** आधी {title} पूर्ण करा.",
        "ben_head": "तुमच्या {n} पात्र योजनांमधून मिळणारी रक्कम:",
        "apply": "बहुतेक शिष्यवृत्त्यांसाठी **राष्ट्रीय शिष्यवृत्ती पोर्टल** (https://scholarships.gov.in/) वर ऑनलाइन अर्ज करतात: मोबाइल नंबरने नोंदणी करा, फॉर्म भरा, कागदपत्रे अपलोड करा, नंतर तुमचे कॉलेज तो तपासते.",
        "jobs": "नोकऱ्यांसाठी **Jobs** पान उघडा: तुमचा रेझ्युमे जोडा, प्रत्येक नोकरीचा फिट स्कोअर आणि शिकण्यासाठी पुढचे कौशल्य पाहा.",
        "hello": "नमस्कार{name}! मी तुमच्या पात्र योजना ({n}), लागणारी कागदपत्रे, शेवटच्या तारखा आणि अर्ज कसा करायचा याबद्दल सांगू शकतो. विचारा: **मी कोणत्या योजनांसाठी पात्र आहे?**",
    },
    "bn": {
        "elig_none": "এখনও আপনি কোনো প্রকল্পের জন্য পুরোপুরি যোগ্য নন। প্রতিটি প্রকল্পে কী কম আছে তা **Schemes**-এ দেখুন।",
        "elig_head1": "আপনি **১টি প্রকল্পের** জন্য যোগ্য:", "elig_head": "আপনি **{n}টি প্রকল্পের** জন্য যোগ্য:",
        "amount_unknown": "পরিমাণ উল্লেখ নেই", "varies": "বিভিন্ন",
        "dl_unknown": "শেষ তারিখ: পোর্টাল দেখুন", "dl_left": "শেষ তারিখ {date} ({d} দিন বাকি)", "dl_closed": "{date}-এ বন্ধ হয়ে গেছে",
        "next_apply": "**পরবর্তী পদক্ষেপ:** প্রথমে {title}-এর জন্য আবেদন করুন", "next_apply_url": "**পরবর্তী পদক্ষেপ:** প্রথমে {title}-এর জন্য আবেদন করুন: {url}",
        "docs_none": "এখন কোনো নথি তৈরি করার দরকার নেই: আপনি কোনো প্রকল্পের জন্য পুরোপুরি যোগ্য নন।",
        "docs_head": "আপনি যে প্রকল্পগুলির জন্য যোগ্য, তার নথি:", "docs_count": "({n}টি প্রকল্পের জন্য)",
        "docs_next": "**পরবর্তী পদক্ষেপ:** **Documents**-এ প্রতিটি নথিতে টিক দিন বা তার ছবি স্ক্যান করুন।",
        "dls_none": "আপনার যোগ্য প্রকল্পগুলির এখন কোনো নির্দিষ্ট শেষ তারিখ নেই। তারিখের জন্য প্রতিটি পোর্টাল দেখুন।",
        "dls_head": "আপনার যোগ্য প্রকল্পগুলির পরবর্তী শেষ তারিখ:", "dls_line": "{date} ({d} দিন বাকি)",
        "dls_next": "**পরবর্তী পদক্ষেপ:** আগে {title} শেষ করুন।",
        "ben_head": "আপনার {n}টি যোগ্য প্রকল্প থেকে যা পাবেন:",
        "apply": "বেশিরভাগ বৃত্তির জন্য **জাতীয় বৃত্তি পোর্টালে** (https://scholarships.gov.in/) অনলাইনে আবেদন করতে হয়: মোবাইল নম্বর দিয়ে নিবন্ধন করুন, ফর্ম পূরণ করুন, নথি আপলোড করুন, তারপর আপনার কলেজ তা যাচাই করে।",
        "jobs": "চাকরির জন্য **Jobs** পাতা খুলুন: আপনার রেজিউমে যোগ করুন, প্রতিটি চাকরির ফিট স্কোর আর শেখার জন্য পরবর্তী দক্ষতা দেখুন।",
        "hello": "নমস্কার{name}! আমি আপনার যোগ্য প্রকল্প ({n}), প্রয়োজনীয় নথি, শেষ তারিখ আর আবেদনের পদ্ধতি নিয়ে বলতে পারি। জিজ্ঞাসা করুন: **আমি কোন প্রকল্পগুলির জন্য যোগ্য?**",
    },
    "te": {
        "elig_none": "ప్రస్తుతం మీరు ఏ పథకానికీ పూర్తిగా అర్హులు కాదు. ప్రతి పథకానికి ఏమి లోటు ఉందో **Schemes** లో చూడండి.",
        "elig_head1": "మీరు **1 పథకానికి** అర్హులు:", "elig_head": "మీరు **{n} పథకాలకు** అర్హులు:",
        "amount_unknown": "మొత్తం పేర్కొనలేదు", "varies": "వేర్వేరు",
        "dl_unknown": "చివరి తేదీ: పోర్టల్ చూడండి", "dl_left": "చివరి తేదీ {date} ({d} రోజులు మిగిలాయి)", "dl_closed": "{date}న ముగిసింది",
        "next_apply": "**తదుపరి అడుగు:** ముందుగా {title} కోసం దరఖాస్తు చేయండి", "next_apply_url": "**తదుపరి అడుగు:** ముందుగా {title} కోసం దరఖాస్తు చేయండి: {url}",
        "docs_none": "ప్రస్తుతం ఏ పత్రాలూ సిద్ధం చేయాల్సిన అవసరం లేదు: మీరు ఏ పథకానికీ పూర్తిగా అర్హులు కాదు.",
        "docs_head": "మీరు అర్హులైన పథకాలకు కావలసిన పత్రాలు:", "docs_count": "({n} పథకాలకు)",
        "docs_next": "**తదుపరి అడుగు:** **Documents** లో ప్రతి పత్రానికి టిక్ పెట్టండి లేదా దాని ఫోటోను స్కాన్ చేయండి.",
        "dls_none": "మీరు అర్హులైన పథకాలకు ప్రస్తుతం నిర్దిష్ట చివరి తేదీ లేదు. తేదీ కోసం ప్రతి పోర్టల్ చూడండి.",
        "dls_head": "మీరు అర్హులైన పథకాల తదుపరి చివరి తేదీలు:", "dls_line": "{date} ({d} రోజులు మిగిలాయి)",
        "dls_next": "**తదుపరి అడుగు:** ముందుగా {title} పూర్తి చేయండి.",
        "ben_head": "మీరు అర్హులైన {n} పథకాల నుంచి లభించేది:",
        "apply": "చాలా స్కాలర్‌షిప్‌లకు **జాతీయ స్కాలర్‌షిప్ పోర్టల్** (https://scholarships.gov.in/) లో ఆన్‌లైన్‌లో దరఖాస్తు చేయాలి: మొబైల్ నంబర్‌తో నమోదు చేసుకోండి, ఫారం నింపండి, పత్రాలు అప్‌లోడ్ చేయండి, తర్వాత మీ కళాశాల దాన్ని ధృవీకరిస్తుంది.",
        "jobs": "ఉద్యోగాల కోసం **Jobs** పేజీ తెరవండి: మీ రెజ్యూమ్ జోడించండి, ప్రతి ఉద్యోగానికి ఫిట్ స్కోర్ మరియు నేర్చుకోవాల్సిన తదుపరి నైపుణ్యం చూడండి.",
        "hello": "నమస్కారం{name}! మీరు అర్హులైన పథకాలు ({n}), కావలసిన పత్రాలు, చివరి తేదీలు మరియు దరఖాస్తు విధానం గురించి చెప్పగలను. అడగండి: **నేను ఏ పథకాలకు అర్హుడిని?**",
    },
    "ta": {
        "elig_none": "இப்போது நீங்கள் எந்தத் திட்டத்துக்கும் முழுமையாகத் தகுதி பெறவில்லை. ஒவ்வொரு திட்டத்துக்கும் என்ன குறைவு என்பதை **Schemes** இல் பாருங்கள்.",
        "elig_head1": "நீங்கள் **1 திட்டத்துக்கு** தகுதியானவர்:", "elig_head": "நீங்கள் **{n} திட்டங்களுக்கு** தகுதியானவர்:",
        "amount_unknown": "தொகை குறிப்பிடப்படவில்லை", "varies": "மாறுபடும்",
        "dl_unknown": "கடைசி தேதி: போர்ட்டலைப் பாருங்கள்", "dl_left": "கடைசி தேதி {date} ({d} நாட்கள் உள்ளன)", "dl_closed": "{date} அன்று முடிந்தது",
        "next_apply": "**அடுத்த படி:** முதலில் {title} க்கு விண்ணப்பியுங்கள்", "next_apply_url": "**அடுத்த படி:** முதலில் {title} க்கு விண்ணப்பியுங்கள்: {url}",
        "docs_none": "இப்போது எந்த ஆவணமும் தயார் செய்யத் தேவையில்லை: நீங்கள் எந்தத் திட்டத்துக்கும் முழுமையாகத் தகுதி பெறவில்லை.",
        "docs_head": "நீங்கள் தகுதியான திட்டங்களுக்குத் தேவையான ஆவணங்கள்:", "docs_count": "({n} திட்டங்களுக்கு)",
        "docs_next": "**அடுத்த படி:** **Documents** இல் ஒவ்வொரு ஆவணத்துக்கும் குறியிடுங்கள் அல்லது அதன் புகைப்படத்தை ஸ்கேன் செய்யுங்கள்.",
        "dls_none": "நீங்கள் தகுதியான திட்டங்களுக்கு இப்போது குறிப்பிட்ட கடைசி தேதி இல்லை. தேதிக்கு ஒவ்வொரு போர்ட்டலையும் பாருங்கள்.",
        "dls_head": "நீங்கள் தகுதியான திட்டங்களின் அடுத்த கடைசி தேதிகள்:", "dls_line": "{date} ({d} நாட்கள் உள்ளன)",
        "dls_next": "**அடுத்த படி:** முதலில் {title} ஐ முடியுங்கள்.",
        "ben_head": "நீங்கள் தகுதியான {n} திட்டங்களில் கிடைப்பது:",
        "apply": "பெரும்பாலான உதவித்தொகைகளுக்கு **தேசிய உதவித்தொகை போர்ட்டலில்** (https://scholarships.gov.in/) ஆன்லைனில் விண்ணப்பிக்க வேண்டும்: மொபைல் எண்ணுடன் பதிவு செய்யுங்கள், படிவத்தை நிரப்புங்கள், ஆவணங்களைப் பதிவேற்றுங்கள், பிறகு உங்கள் கல்லூரி அதைச் சரிபார்க்கும்.",
        "jobs": "வேலைகளுக்கு **Jobs** பக்கத்தைத் திறங்கள்: உங்கள் ரெஸ்யூமைச் சேர்த்து, ஒவ்வொரு வேலையின் பொருத்த மதிப்பெண்ணையும் கற்க வேண்டிய அடுத்த திறனையும் பாருங்கள்.",
        "hello": "வணக்கம்{name}! நீங்கள் தகுதியான திட்டங்கள் ({n}), தேவையான ஆவணங்கள், கடைசி தேதிகள், விண்ணப்பிக்கும் முறை பற்றிச் சொல்ல முடியும். கேளுங்கள்: **நான் எந்தத் திட்டங்களுக்குத் தகுதியானவன்?**",
    },
}

DIGITS = {"bn": "০১২৩৪৫৬৭৮৯"}


def _num(lang: str, n: int) -> str:
    """Bengali writes counts in Bengali digits; the others use 0-9 in this app."""
    d = DIGITS.get(lang)
    return "".join(d[int(c)] for c in str(n)) if d else str(n)


def keyword_intent(question: str, lang: str) -> str | None:
    q = (question or "").lower()
    for label, words in KEYWORDS.get(lang, {}).items():
        if any(w in q for w in words):
            return label
    return None


def _days_left(deadline: str | None) -> int | None:
    try:
        return (date.fromisoformat(deadline or "") - date.today()).days
    except ValueError:
        return None


def answer(lang: str, intent: str, eligible: list[dict], profile: dict | None) -> str | None:
    """An answer in `lang` for the common question types, or None to fall back to English."""
    t = T.get(lang)
    if not t:
        return None
    f = lambda key, **kw: t[key].format(**kw)

    def when(m):
        d = _days_left(m.get("deadline"))
        if d is None:
            return t["dl_unknown"]
        return f("dl_left", date=m["deadline"], d=_num(lang, d)) if d >= 0 else f("dl_closed", date=m["deadline"])

    if intent == "eligibility":
        if not eligible:
            return t["elig_none"]
        ordered = sorted(eligible, key=lambda m: (_days_left(m.get("deadline")) is None, _days_left(m.get("deadline")) or 0))
        n = len(eligible)
        lines = [t["elig_head1"] if n == 1 else f("elig_head", n=_num(lang, n)), ""]
        lines += [f"• **{m['title']}**: {m.get('amount') or t['amount_unknown']} · {when(m)}" for m in ordered[:6]]
        first = ordered[0]
        lines += ["", f("next_apply_url", title=first["title"], url=first["url"]) if first.get("url") else f("next_apply", title=first["title"]) + ("।" if lang in ("hi", "bn") else ".")]
        return "\n".join(lines)
    if intent == "documents":
        with_docs = [m for m in eligible if m.get("documents")]
        if not with_docs:
            return t["docs_none"]
        count: dict[str, int] = {}
        for m in with_docs:
            for d in m["documents"]:
                count[d] = count.get(d, 0) + 1
        lines = [t["docs_head"], ""]
        lines += [f"• {d}" + (" " + f("docs_count", n=_num(lang, count[d])) if count[d] > 1 else "")
                  for d in sorted(count, key=lambda d: -count[d])[:10]]
        lines += ["", t["docs_next"]]
        return "\n".join(lines)
    if intent == "deadlines":
        dated = sorted(((d, m) for m in eligible if (d := _days_left(m.get("deadline"))) is not None and d >= 0), key=lambda x: x[0])
        if not dated:
            return t["dls_none"]
        lines = [t["dls_head"], ""]
        lines += [f"• **{m['title']}**: " + f("dls_line", date=m["deadline"], d=_num(lang, d)) + (" ⚠️" if d <= 7 else "") for d, m in dated[:5]]
        lines += ["", f("dls_next", title=dated[0][1]["title"])]
        return "\n".join(lines)
    if intent == "benefits" and eligible:
        lines = [f("ben_head", n=_num(lang, len(eligible))), ""]
        lines += [f"• **{m['title']}**: {m.get('amount') or t['varies']}" for m in eligible[:6]]
        return "\n".join(lines)
    if intent == "how_to_apply":
        return t["apply"]
    if intent == "jobs":
        return t["jobs"]
    if intent == "other":
        name = profile["name"].split()[0] if profile and profile.get("name") else ""
        return f("hello", name=(" " + name) if name else "", n=_num(lang, len(eligible)))
    return None
