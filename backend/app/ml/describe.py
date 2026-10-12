"""Turn one sentence about yourself into profile fields.

    "I'm Aisha, a 21-year-old girl from Bengaluru doing B.Tech in computer science,
     OBC, family income 3 lakh, I want a job"
    → name Aisha, age 21, gender Female, state Karnataka, education Undergraduate,
      field Computer Science, category OBC, income 300000, goals job

Numbers come from patterns (age, income in lakh/thousand/rupees, disability %);
the rest from word lists in English, Hindi and Hinglish. Every field says which
words it came from, so the user can check before saving.
"""
from __future__ import annotations

import re

from app.jobs.locations import STATE_CITIES, find_state

EDUCATION = [
    (r"\bph\.?\s?d\b|doctorate", "Postgraduate"),
    (r"\bm\.?\s?tech\b|\bm\.?\s?sc\b|\bmba\b|\bmca\b|\bm\.?\s?com\b|\bm\.?\s?a\b|master'?s|post\s?graduat|\bpg\b", "Postgraduate"),
    (r"\bb\.?\s?tech\b|\bb\.?\s?e\b|\bb\.?\s?sc\b|\bbca\b|\bbba\b|\bb\.?\s?com\b|\bb\.?\s?a\b|\bmbbs\b|\bllb\b|bachelor|graduat|college|degree|undergrad|\bug\b|स्नातक|बी\.?\s?(?:टेक|कॉम|एससी|ए)|कॉलेज", "Undergraduate"),
    (r"\bdiploma\b|polytechnic|\biti\b|डिप्लोमा", "Diploma"),
    (r"\b12(?:th)?\b|class\s*12|\bxii\b|intermediate|higher secondary|\bpuc\b|बारहवीं|12वीं", "12th"),
    (r"\b11(?:th)?\b|class\s*11|\bxi\b|11वीं", "11th"),
    (r"\b10(?:th)?\b|class\s*10|\bsslc\b|matric|दसवीं|10वीं", "10th"),
    (r"\b9(?:th)?\b|class\s*9|9वीं", "9th"),
]
FIELDS = [
    (r"computer|\bcse\b|\bit\b|software|\bbca\b|\bmca\b", "Computer Science"),
    (r"engineer|टेक|इंजीनियर|b\.?\s?tech|\bb\.?\s?e\b|mechanical|civil|electrical|electronics|\bece\b|\beee\b", "Engineering"),
    (r"medic|mbbs|nursing|pharma|\bbds\b|health", "Medical"),
    (r"commerce|b\.?\s?com|m\.?\s?com|account|finance|\bca\b|कॉम|वाणिज्य", "Commerce"),
    (r"management|\bbba\b|\bmba\b|business", "Management"),
    (r"science|physics|chemistry|biology|maths|mathematics|b\.?\s?sc", "Science"),
    (r"\blaw\b|\bllb\b", "Law"),
    (r"arts|humanities|history|english|political|economics|\bb\.?\s?a\b", "Arts"),
]
CATEGORIES = [(r"\bobc\b|other backward|ओबीसी|पिछड़ा", "OBC"), (r"\bsc\b|scheduled caste|dalit|एससी|अनुसूचित जाति", "SC"),
              (r"\bst\b|scheduled tribe|adivasi|tribal|एसटी|अनुसूचित जनजाति", "ST"),
              (r"\bews\b|economically weaker", "EWS"), (r"\bgeneral\b|\bgen\b|unreserved", "General")]
FEMALE = r"\b(?:girl|woman|female|she|her|daughter|lady|ladki|beti)\b|लड़की|महिला|बेटी"
MALE = r"\b(?:boy|man|male|he|his|son|ladka|beta)\b|लड़का|बेटा|पुरुष"
HINDI_STATES = {"उत्तर प्रदेश": "Uttar Pradesh", "बिहार": "Bihar", "राजस्थान": "Rajasthan", "मध्य प्रदेश": "Madhya Pradesh",
                "महाराष्ट्र": "Maharashtra", "दिल्ली": "Delhi", "कर्नाटक": "Karnataka", "गुजरात": "Gujarat", "हरियाणा": "Haryana",
                "पंजाब": "Punjab", "झारखंड": "Jharkhand", "उत्तराखंड": "Uttarakhand", "पश्चिम बंगाल": "West Bengal",
                "तमिलनाडु": "Tamil Nadu", "केरल": "Kerala", "ओडिशा": "Odisha", "छत्तीसगढ़": "Chhattisgarh", "असम": "Assam",
                "तेलंगाना": "Telangana", "आंध्र प्रदेश": "Andhra Pradesh", "हिमाचल प्रदेश": "Himachal Pradesh"}
# Values match the goal chips in onboarding
GOALS = [(r"\bjob|naukri|नौकरी|placement|career|work\b", "get a job"),
         (r"higher stud|study|studies|masters|pg\b|पढ़ाई|padhai|further education", "higher studies"),
         (r"business|startup|start-up|entrepreneur|व्यवसाय|dhanda", "start a business"),
         (r"skill|course|training|learn|सीखना", "learn a skill")]


def _income(text: str) -> tuple[int, str] | None:
    low = text.lower().replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(lakh|lac|lakhs|lpa|l\b|लाख)", low)
    if m:
        return int(float(m.group(1)) * 100_000), m.group(0)
    m = re.search(r"(\d+(?:\.\d+)?)\s*(k|thousand|हज़ार|hazar)\b", low)
    if m:
        return int(float(m.group(1)) * 1000), m.group(0)
    m = re.search(r"(?:₹|rs\.?|inr|income|earn\w*)\s*(?:of|is|:)?\s*(\d{5,8})", low)
    if m:
        return int(m.group(1)), m.group(0)
    return None


# Words that end a name ("I'm Aisha from Pune", "I am a student")
_NOT_NAME = {"a", "an", "the", "from", "doing", "studying", "in", "and", "i", "im", "am", "my", "student", "girl", "boy",
             "woman", "man", "studying", "pursuing", "currently", "living", "based", "here", "with", "of", "at", "to",
             "female", "male", "not", "also", "looking", "years", "year", "yrs", "old", "aged", "age", "is", "was",
             "interested", "working", "unemployed", "fresher", "graduate", "engineer", "obc", "sc", "st", "ews",
             "general", "very", "so", "really", "currently", "hoping", "trying", "planning", "going", "applying"}


def _name(t: str) -> tuple[str | None, str]:
    """The person's name, however the apostrophe or capitals are typed:
    "I'm Aisha Kumar", "I’m aisha", "I am Rohan", "my name is meera patil", "Name: Arjun", "मेरा नाम राहुल"."""
    s = t.replace("’", "'").replace("‘", "'").replace("`", "'")
    m = re.search(r"मेरा नाम\s+([\u0900-\u097F]+(?:\s+[\u0900-\u097F]+)?)", s)
    if m:
        return m.group(1).strip().removesuffix(" है").strip(), m.group(0)
    m = re.search(r"(?:\bi'?m\b|\bi am\b|\bmy name is\b|\bname\s*[:\-]|\bmera naam\b|\bthis is\b)\s*([A-Za-z][A-Za-z.]*(?:\s+[A-Za-z][A-Za-z.]*){0,3})", s, re.I)
    if not m:
        m = re.match(r"\s*([A-Z][a-z]+\s+[A-Z][a-z]+)\s*,", s)   # "Aisha Kumar, 21, ..."
    if not m:
        return None, ""
    words = []
    for w in m.group(1).split():
        if w.lower().strip(".") in _NOT_NAME or any(ch.isdigit() for ch in w):
            break
        words.append(w.strip("."))
        if len(words) == 3:
            break
    if not words:
        return None, ""
    return " ".join(w[:1].upper() + w[1:] for w in words), m.group(0)


def describe(text: str) -> dict:
    """{"profile": {...fields found...}, "found": [{"field", "value", "from"}], "missing": [...]}"""
    t = " " + (text or "").strip() + " "
    low = t.lower()
    prof: dict = {}
    found: list[dict] = []

    def put(field, value, source):
        if value is not None and field not in prof:
            prof[field] = value
            found.append({"field": field, "value": value, "from": source.strip()})

    name, src = _name(t)
    if name:
        put("name", name, src)

    m = re.search(r"(\d{1,2})\s*(?:-|\s)?\s*(?:years?|yrs?|yo|साल|saal)(?:\s*-?\s*old)?|age\s*(?:is|:)?\s*(\d{1,2})|उम्र\s*(\d{1,2})", low)
    if m:
        age = int(next(g for g in m.groups() if g))
        if 5 <= age <= 100:
            put("age", age, m.group(0))

    m = re.search(FEMALE, low)
    if m:
        put("gender", "Female", m.group(0))
    else:
        m = re.search(MALE, low)
        if m:
            put("gender", "Male", m.group(0))

    state = find_state(t)
    if not state:
        hit = next((h for h in HINDI_STATES if h in t), None)
        if hit:
            put("state", HINDI_STATES[hit], hit)
    if state:
        word = next((s for s in [state.lower(), *STATE_CITIES.get(state, [])] if re.search(rf"\b{re.escape(s)}\b", low)), state)
        put("state", state, word)

    for pat, cat in CATEGORIES:
        m = re.search(pat, low)
        if m:
            put("category", cat, m.group(0))
            break

    for pat, level in EDUCATION:
        m = re.search(pat, low)
        if m:
            put("education_level", level, m.group(0))
            break

    for pat, field in FIELDS:
        m = re.search(pat, low)
        if m:
            put("field_of_study", field, m.group(0))
            break

    inc = _income(t)
    if inc:
        put("annual_income", inc[0], inc[1])

    m = re.search(r"disab\w*|handicap\w*|divyang|दिव्यांग|(\d{2})\s*%\s*disab", low)
    if m and not re.search(r"\bno disab|not disab|without disab", low):
        pct = re.search(r"(\d{2})\s*%", low)
        if not pct or int(pct.group(1)) >= 40:
            put("disability", True, m.group(0))

    goals = [g for pat, g in GOALS if re.search(pat, low)]
    if goals:
        put("goals", ", ".join(dict.fromkeys(goals)), ", ".join(goals))

    wanted = ["name", "age", "gender", "state", "category", "education_level", "field_of_study", "annual_income"]
    return {"profile": prof, "found": found, "missing": [f for f in wanted if f not in prof]}
