"""Build the seed datasets in app/ml/data/.

    python -m app.ml.make_data

Every file is plain CSV or JSON so the team can open, check and relabel it.
The seed data is generated from written templates and labelling rules
(see app/ml/data/LABELLING.md); it is a starting point, not hand-labelled
ground truth. Labels added in the ML Lab's Label tab are kept in
fit_pairs_team.csv and always override the seed labels.

The generator is seeded, so running it again gives the same files.
"""
from __future__ import annotations

import csv
import json
import random
from pathlib import Path

from app.jobs.catalog import families
from app.jobs.jobparse import analyse_job
from app.jobs.sources import sample_jobs

DATA = Path(__file__).resolve().parent / "data"
rng = random.Random(42)

# ── 1. Job descriptions by role family ───────────────────────────────

DUTIES = {
    "software": ["solve problems in code and review pull requests", "write clean, tested code for product features",
                 "work with the team on design discussions", "debug issues reported by users"],
    "backend": ["build APIs used by web and mobile apps", "design database tables and queries",
                "keep services fast and reliable", "write server-side business logic"],
    "frontend": ["build responsive web pages from Figma designs", "make the user interface fast and accessible",
                 "turn designs into reusable components", "fix layout bugs across browsers"],
    "fullstack": ["build features end to end, from database to screen", "own both the API and the web app",
                  "ship complete product features", "work across client and server code"],
    "mobile": ["build Android apps used by thousands of customers", "publish releases on the Play Store",
               "fix crashes and improve app performance", "build mobile screens from designs"],
    "data_analyst": ["prepare weekly sales reports and dashboards", "analyse business data to find trends",
                     "clean and combine data from many sheets", "present insights to managers"],
    "data_scientist": ["train and evaluate machine learning models", "build features from raw data",
                       "run experiments and measure model accuracy", "deploy prediction models"],
    "devops": ["manage cloud servers and deployments", "automate build and release pipelines",
               "monitor uptime and fix production incidents", "manage containers and infrastructure"],
    "qa": ["write and run test cases for every release", "find, log and track bugs",
           "automate regression tests", "check that features meet requirements"],
    "design": ["design app screens and user flows", "create social media creatives and banners",
               "build wireframes and prototypes", "run usability tests with users"],
    "accounts": ["maintain books of accounts", "file GST returns every month", "prepare invoices and reconcile bank statements",
                 "support the yearly audit"],
    "sales": ["meet new clients and close deals", "achieve monthly sales targets", "generate leads by calling and visiting customers",
              "maintain relationships with dealers"],
    "marketing": ["run social media and ad campaigns", "plan marketing campaigns and track results",
                  "grow website traffic with SEO", "manage the brand's online presence"],
    "content": ["write blogs, articles and website copy", "edit and proofread content", "research topics and write clear explainers",
                "write scripts for videos"],
    "hr": ["handle recruitment from screening to joining", "manage employee onboarding and records", "coordinate interviews",
           "support payroll and HR policies"],
    "support": ["answer customer calls and chats", "resolve customer complaints politely", "raise tickets and follow up",
                "help customers use the product"],
    "operations": ["manage stock in the warehouse", "plan dispatch and deliveries", "coordinate with vendors and transporters",
                   "track orders and daily operations"],
    "teaching": ["teach classes and prepare lesson plans", "check homework and conduct tests", "explain concepts to students",
                 "talk to parents about student progress"],
    "healthcare": ["care for patients in the ward", "record vital signs and give medicines", "assist doctors during rounds",
                   "keep patient records up to date"],
    "office": ["enter data accurately into the system", "maintain files and records", "prepare reports in Excel",
               "handle front office and calls"],
    "engineering": ["prepare drawings and designs", "supervise work at site", "check quality of materials and work",
                    "coordinate with contractors"],
}
TITLES = {
    "software": ["Software engineer", "Software developer", "SDE 1", "Programmer", "Graduate software engineer"],
    "backend": ["Backend developer", "Python developer", "Java developer", "API developer", "Node.js backend engineer"],
    "frontend": ["Frontend developer", "React developer", "UI developer", "Web developer (frontend)", "Angular developer"],
    "fullstack": ["Full-stack developer", "MERN stack developer", "Full stack engineer", "Web application developer"],
    "mobile": ["Android developer", "Mobile app developer", "Flutter developer", "iOS developer"],
    "data_analyst": ["Data analyst", "MIS executive", "Business analyst", "Reporting analyst", "Junior data analyst"],
    "data_scientist": ["Data scientist", "Machine learning engineer", "ML intern", "AI engineer", "NLP engineer"],
    "devops": ["DevOps engineer", "Cloud engineer", "Site reliability engineer", "System administrator"],
    "qa": ["QA engineer", "Software tester", "Test automation engineer", "QA analyst"],
    "design": ["UI/UX designer", "Graphic designer", "Product designer", "Visual designer"],
    "accounts": ["Accountant", "Accounts executive", "Tax associate", "Accounts assistant", "Audit assistant"],
    "sales": ["Sales executive", "Business development executive", "Field sales officer", "Inside sales associate"],
    "marketing": ["Digital marketing executive", "Marketing associate", "SEO executive", "Social media manager"],
    "content": ["Content writer", "Copywriter", "Technical writer", "Content editor"],
    "hr": ["HR executive", "Recruiter", "Talent acquisition associate", "HR assistant"],
    "support": ["Customer support associate", "Customer care executive", "Call centre executive", "Technical support"],
    "operations": ["Operations executive", "Warehouse supervisor", "Logistics coordinator", "Supply chain executive"],
    "teaching": ["Teacher", "Online tutor", "Primary school teacher", "Maths teacher"],
    "healthcare": ["Staff nurse", "Nursing assistant", "Patient care executive", "Ward nurse"],
    "office": ["Data entry operator", "Office assistant", "Back office executive", "Computer operator"],
    "engineering": ["Site engineer", "Civil engineer", "Mechanical design engineer", "Junior engineer"],
}
EXTRA_SKILLS = {
    "software": ["C++", "JavaScript", "System Design", "Linux"], "backend": ["Django", "FastAPI", "Docker", "Spring Boot", "MySQL"],
    "frontend": ["TypeScript", "Tailwind CSS", "Next.js", "Figma"], "fullstack": ["MongoDB", "Express", "TypeScript", "Docker"],
    "mobile": ["Java", "Flutter", "Dart", "REST APIs"], "data_analyst": ["Python", "Tableau", "MS Office"],
    "data_scientist": ["NumPy", "scikit-learn", "Deep Learning", "NLP", "TensorFlow"], "devops": ["Kubernetes", "Terraform", "Bash", "Python"],
    "qa": ["Java", "Agile", "Git"], "design": ["Illustrator", "HTML", "CSS"], "accounts": ["Taxation", "Auditing", "MS Office"],
    "sales": ["English", "Hindi", "MS Office"], "marketing": ["Communication", "Video Editing"], "content": ["Marketing", "Canva"],
    "hr": ["Excel", "English", "Negotiation"], "support": ["Hindi", "CRM"], "operations": ["MS Office", "Negotiation"],
    "teaching": ["MS Office", "Hindi"], "healthcare": ["English", "Hindi"], "office": ["Hindi", "Communication"],
    "engineering": ["SolidWorks", "Project Management", "Excel"],
}
BOILER = ["We are a growing company in {city}.", "Immediate joiners preferred.", "Good communication is a plus.",
          "Work from office, 5 days a week.", "Salary as per industry standards.", "Freshers can also apply.",
          "Join a friendly and fast-moving team.", "Location: {city}.", ""]
CITIES = ["Bengaluru", "Pune", "Hyderabad", "Delhi", "Mumbai", "Chennai", "Noida", "Kolkata", "Jaipur", "Lucknow", "Indore", "Kochi"]


def _job_text(fam_key: str) -> str:
    fam = families()[fam_key]
    title = rng.choice(TITLES[fam_key])
    core = rng.sample(fam["core"], k=min(len(fam["core"]), rng.randint(2, len(fam["core"]))))
    extra = rng.sample(EXTRA_SKILLS[fam_key], k=rng.randint(0, min(2, len(EXTRA_SKILLS[fam_key]))))
    duty = rng.sample(DUTIES[fam_key], k=2)
    years = rng.choice(["0-1 years", "1-3 years", "2-4 years", "Freshers", "0-2 years", "3+ years"])
    parts = [f"{title}.", f"You will {duty[0]} and {duty[1]}.", f"Requirements: {', '.join(core)}."]
    if extra:
        parts.append(f"Good to have: {', '.join(extra)}.")
    parts.append(f"Experience: {years}.")
    parts.append(rng.choice(BOILER).format(city=rng.choice(CITIES)))
    return " ".join(p for p in parts if p)


def make_role_jobs(per_family: int = 24) -> list[dict]:
    rows = [{"text": f"{j['title']}. {j['description']}", "family": j["family"], "source": "curated sample role"} for j in sample_jobs()]
    for key in families():
        for _ in range(per_family):
            rows.append({"text": _job_text(key), "family": key, "source": "template"})
    rng.shuffle(rows)
    return rows


# ── 2. Resume–job pairs labelled Good / Okay / Poor ─────────────────

LEVELS = ["12th", "Diploma", "Undergraduate", "Postgraduate"]


def _resume(fam_key: str, quality: float) -> tuple[str, dict]:
    """A short synthetic resume for someone aiming at `fam_key`; quality 0..1 sets how many core skills and how proved."""
    fam = families()[fam_key]
    pool = fam["core"] + EXTRA_SKILLS[fam_key]
    k = max(1, round(len(pool) * quality * rng.uniform(0.6, 1.0)))
    skills = rng.sample(pool, k=min(k, len(pool)))
    worked = [s for s in skills if rng.random() < quality * 0.6]
    project = [s for s in skills if s not in worked and rng.random() < 0.6]
    listed = [s for s in skills if s not in worked and s not in project]
    years = rng.choice([0, 0, 0, 0.5, 1, 2, 3, 5]) if quality > 0.3 else rng.choice([0, 0, 1])
    lines = ["Candidate", "Skills", ", ".join(listed or skills[:1])]
    if worked:
        start = 2026 - max(1, int(years))
        lines += ["Experience", f"{rng.choice(TITLES[fam_key])}, Acme Pvt Ltd  Jan {start} - present" if years >= 1
                  else "Intern, Acme Pvt Ltd  Jun 2025 - Aug 2025", f"Worked with {', '.join(worked)}"]
    if project:
        lines += ["Projects", f"Built a small project using {', '.join(project)}"]
    level = rng.choice(LEVELS[1:]) if quality > 0.3 else rng.choice(LEVELS)
    lines += ["Education", {"12th": "Class 12th, 2022", "Diploma": "Diploma in engineering 2023",
                            "Undergraduate": "B.Tech / B.Com / B.Sc 2021-2025", "Postgraduate": "MBA / M.Tech 2024"}[level]]
    return "\n".join(lines), {"education_level": level}


def rubric(job: dict, cand: dict, a: dict) -> str:
    """The written labelling rules (LABELLING.md), applied to facts about the pair."""
    strength = cand["strength"]
    units = a["must_units"]
    have = [u for u in units if any(strength.get(s, 0) for s in u)]
    proved = [u for u in have if any(strength.get(s, 0) >= 2 for s in u)]
    coverage = len(have) / len(units) if units else 0
    same_kind = a["family"] is not None and a["family"] == cand["target_family"]
    need = a["min_years"] or 0
    edu_ok = not a["education"] or cand["level"] is None or cand["level"] >= a["education"][0]
    if not edu_ok or need - cand["years"] >= 3 or (not same_kind and coverage < 0.4):
        return "Poor"
    if same_kind and coverage >= 0.75 and len(proved) >= len(have) / 2 and need - cand["years"] <= 1:
        return "Good"
    return "Okay"


def make_fit_pairs(n: int = 260) -> list[dict]:
    from app.jobs import matching
    from app.jobs.matching import candidate, score_with
    matching.weights = lambda: matching.HAND_WEIGHTS   # "rules_fit" is always the old hand-set score
    # The data must not depend on a model trained from it: use the keyword role rules here
    from app.jobs import catalog
    matching.classify_role = catalog.classify_role_rules
    jobs = [{"title": j["title"], "description": j["description"], "family": j["family"]} for j in sample_jobs()]
    rows = []
    keys = list(families())
    per_label = {"Good": 0, "Okay": 0, "Poor": 0}
    tries = 0
    # Balanced classes: about a third each, so accuracy is not won by always saying "Poor"
    while len(rows) < n and tries < n * 60:
        tries += 1
        job = dict(rng.choice(jobs))
        if rng.random() < 0.3:
            # Some senior versions of the same role, so experience gaps are in the data
            import re as _re
            job["title"] = "Senior " + job["title"][0].lower() + job["title"][1:]
            job["description"] = _re.sub(r"Experience:[^.]*\.", f"Experience: {rng.choice([3, 4, 5, 6])}+ years.", job["description"])
        # Most candidates aim at the job's own family; some at a neighbour or something unrelated
        fam_key = job["family"] if rng.random() < 0.65 else rng.choice(keys)
        text, profile = _resume(fam_key, rng.uniform(0.2, 1.0))
        cand = candidate(profile, text, desired_role=families()[fam_key]["label"])
        a = analyse_job(job)
        s = score_with(job, cand, a)
        feats = {b["signal"]: b["value"] for b in s["fit_breakdown"]}
        label = rubric(job, cand, a)
        if per_label[label] >= n // 3 + 1:
            continue
        per_label[label] += 1
        rows.append({
            "job_title": job["title"], "job_text": job["description"], "resume_text": text,
            "education_level": profile["education_level"], "target_role": families()[fam_key]["label"],
            **{f: feats.get(f, "") for f in ("must", "nice", "role", "experience", "education", "field", "text")},
            "rules_fit": s["fit_score"], "label": label,
        })
    return rows


# ── 3. Assistant intents (English, Hindi, Hinglish) ──────────────────

INTENTS = {
    "eligibility": [
        "Which schemes do I qualify for?", "Am I eligible for any scholarship?", "What scholarships can I get?",
        "Do I qualify for AICTE Pragati?", "Show me schemes I can apply for", "Can I get the merit scholarship?",
        "Which government schemes are for me?", "Am I eligible for the OBC scholarship?", "What am I eligible for",
        "Is there any scheme for girls like me?", "Will I get the post matric scholarship?", "Which grants fit my profile?",
        "मैं किन योजनाओं के लिए पात्र हूँ?", "क्या मुझे छात्रवृत्ति मिल सकती है?", "मेरे लिए कौन सी योजनाएँ हैं?",
        "क्या मैं प्रगति स्कॉलरशिप के लिए योग्य हूँ?", "kaun si scheme mere liye hai", "kya main eligible hoon",
        "mujhe kaunsi scholarship milegi", "kya mujhe yojana ka labh milega", "which schemes match me", "eligible schemes list",
    ],
    "documents": [
        "What documents do I need?", "Which papers should I keep ready?", "Documents required for the scholarship",
        "Do I need an income certificate?", "What do I upload for AICTE Pragati?", "List of documents to apply",
        "Is Aadhaar required?", "Which certificates are needed for the OBC scholarship?", "What proof do I need to show?",
        "Do I need a caste certificate?", "checklist of documents", "what should I scan before applying",
        "कौन से दस्तावेज़ चाहिए?", "आवेदन के लिए कौन से कागज़ात लगेंगे?", "क्या आय प्रमाण पत्र ज़रूरी है?",
        "दस्तावेज़ों की सूची बताइए", "kaun kaun se documents lagenge", "kagaz kya kya chahiye", "income certificate chahiye kya",
        "aadhaar zaroori hai kya", "documents needed", "which documents for startup india",
    ],
    "deadlines": [
        "When is the last date?", "What are the upcoming deadlines?", "When does the Pragati scholarship close?",
        "Is the merit scholarship still open?", "How many days are left to apply?", "Next deadline please",
        "When should I apply by?", "Which scheme closes first?", "Has the deadline passed?", "deadline for post matric scholarship",
        "What is the closing date for NSP?", "Remind me of the dates", "अंतिम तिथि क्या है?", "आवेदन की आखिरी तारीख कब है?",
        "कौन सी योजना सबसे पहले बंद होगी?", "कितने दिन बचे हैं?", "last date kab hai", "deadline kab tak hai",
        "kitne din bache hain apply karne ke", "form kab tak bharna hai", "closing dates", "when do applications end",
    ],
    "benefits": [
        "How much money will I get?", "What is the scholarship amount?", "How much is the Pragati scholarship?",
        "What are the benefits?", "Total value of my schemes", "How much can I get per year?", "Does it pay tuition fees?",
        "What does the startup seed fund give?", "Is there a stipend?", "amount for merit scholarship", "how much grant",
        "What will I receive if selected?", "मुझे कितने पैसे मिलेंगे?", "छात्रवृत्ति की राशि कितनी है?", "इस योजना से क्या लाभ है?",
        "सालाना कितना मिलेगा?", "kitna paisa milega", "scholarship amount kitna hai", "kya fayda hai is scheme ka",
        "kitne rupaye milenge", "benefit amount", "value of the scholarships",
    ],
    "how_to_apply": [
        "How do I apply?", "Where do I apply for AICTE Pragati?", "What is the application process?", "Steps to apply for NSP",
        "Give me the link to apply", "How to register on the national scholarship portal?", "Can I apply online?",
        "Where is the application form?", "How do I fill the form?", "What happens after I apply?", "apply link please",
        "Who verifies my application?", "आवेदन कैसे करें?", "फॉर्म कहाँ भरना है?", "आवेदन की प्रक्रिया क्या है?",
        "ऑनलाइन आवेदन कैसे करूँ?", "apply kaise karein", "form kaha bharna hai", "registration kaise hoga",
        "link do apply karne ka", "application steps", "how to submit the form",
    ],
    "jobs": [
        "Which jobs suit me?", "Find me a job", "What jobs can I get with my resume?", "How do I become a data analyst?",
        "Which skills should I learn for a job?", "Show me jobs near me", "Is there any internship for me?",
        "How can I get a software job?", "What should I learn next for my career?", "Job roadmap please",
        "Am I ready for a backend developer job?", "Which companies are hiring freshers?", "मेरे लिए कौन सी नौकरी है?",
        "नौकरी के लिए कौन सा कौशल सीखूँ?", "क्या मेरे लिए कोई इंटर्नशिप है?", "नौकरी कैसे मिलेगी?", "mujhe job chahiye",
        "kaunsi naukri mil sakti hai", "job ke liye kya seekhna chahiye", "internship kaha milegi", "career advice",
        "jobs for my skills",
    ],
}


INTENTS["other"] = [
    "hello", "hi", "hello how are you", "good morning", "thanks", "thank you so much", "who are you?", "what can you do?",
    "ok", "bye", "namaste", "kaise ho", "shukriya", "aap kaun ho", "नमस्ते", "धन्यवाद", "आप कौन हैं?", "आप क्या कर सकते हैं?",
    "tell me a joke", "what is your name?", "nice", "good night", "help", "how does this app work?",
]


def _vary(q: str) -> list[str]:
    """The question as written, plus lower-case and no-punctuation versions people actually type."""
    out = {q, q.lower(), q.rstrip("?।").strip()}
    return sorted(out)


def make_intents() -> list[dict]:
    rows = []
    for intent, qs in INTENTS.items():
        for q in qs:
            for v in _vary(q)[:2]:
                rows.append({"text": v, "intent": intent, "lang": "hi" if any("ऀ" <= ch <= "ॿ" for ch in v) else "en"})
    rng.shuffle(rows)
    return rows


# ── 4. Document text (what OCR reads from a certificate) ─────────────

NAMES = ["Aisha Kumar", "Rohit Sharma", "Priya Singh", "Mohammed Irfan", "Lakshmi N", "Arjun Reddy", "Sneha Patil",
         "Rahul Verma", "Fatima Shaikh", "Vikram Yadav", "Anjali Gupta", "Karthik S"]
STATES = ["Karnataka", "Uttar Pradesh", "Maharashtra", "Delhi", "Tamil Nadu", "Bihar", "Rajasthan", "West Bengal"]
DOC_TEMPLATES = {
    "aadhaar": ["Government of India {name} DOB: {dob} {gender} XXXX XXXX {d4} Aadhaar Mera Aadhaar Meri Pehchaan",
                "UNIQUE IDENTIFICATION AUTHORITY OF INDIA {name} Year of Birth {year} {gender} Address {state} XXXX XXXX {d4}",
                "भारत सरकार {name} जन्म तिथि {dob} आधार - आम आदमी का अधिकार XXXX XXXX {d4}"],
    "income": ["INCOME CERTIFICATE This is to certify that {name} resident of {state} has an annual family income of Rs. {inc} from all sources. Tehsildar",
               "Government of {state} Revenue Department Income Certificate Certificate No {num} Annual income Rs {inc} Issued on {date}",
               "आय प्रमाण पत्र प्रमाणित किया जाता है कि {name} की वार्षिक पारिवारिक आय {inc} रुपये है। तहसीलदार"],
    "caste": ["CASTE CERTIFICATE This is to certify that {name} belongs to the {caste} community which is recognised as {cat} Sub Divisional Officer",
              "Government of {state} Other Backward Classes certificate (non creamy layer) {name} Certificate No {num} Issued {date}",
              "जाति प्रमाण पत्र प्रमाणित किया जाता है कि {name} {cat} जाति से संबंधित है। अनुमंडल पदाधिकारी"],
    "domicile": ["DOMICILE CERTIFICATE This is to certify that {name} is a permanent resident of {state} and has been residing for {yrs} years",
                 "Residence Certificate Government of {state} {name} resident of district since {year} Certificate No {num}",
                 "निवास प्रमाण पत्र प्रमाणित किया जाता है कि {name} {state} राज्य के स्थायी निवासी हैं।"],
    "disability": ["DISABILITY CERTIFICATE This is to certify that {name} is a case of locomotor disability with {pct}% permanent physical impairment Medical Board",
                   "Unique Disability ID UDID Card {name} Disability Type Visual impairment Percentage {pct}% Valid upto {date}",
                   "दिव्यांगता प्रमाण पत्र {name} स्थायी दिव्यांगता {pct}% चिकित्सा बोर्ड"],
    "marksheet": ["Central Board of Secondary Education Marks Statement {name} Roll No {num} English {m1} Mathematics {m2} Physics {m3} Result PASS",
                  "STATEMENT OF MARKS University Semester Examination {name} SGPA {sgpa} CGPA {sgpa} Subject Code Marks Obtained {m1}",
                  "अंक पत्र माध्यमिक शिक्षा परिषद {name} अनुक्रमांक {num} कुल अंक {m1} परिणाम उत्तीर्ण"],
    "bank_passbook": ["STATE BANK OF INDIA Savings Account Passbook Customer Name {name} Account No XXXXXX{d4} IFSC SBIN000{d4} Branch {state}",
                      "Bank of Baroda Passbook {name} A/c No XXXXXXXX{d4} IFSC BARB0{d4} MICR Date Particulars Withdrawals Deposits Balance",
                      "पासबुक बचत खाता {name} खाता संख्या XXXXXX{d4} आईएफएससी कोड शाखा"],
    "fee_receipt": ["FEE RECEIPT {college} Receipt No {num} Received from {name} the sum of Rs {fee} towards tuition fee for the year {year}",
                    "Payment Receipt Student Name {name} Course B.Tech Semester Fee Rs {fee} Mode Online Transaction ID {num} {college}",
                    "शुल्क रसीद {college} छात्र का नाम {name} शिक्षण शुल्क {fee} रुपये प्राप्त"],
}
COLLEGES = ["Government Engineering College", "St. Joseph's College", "Delhi University", "Anna University", "Pune Institute of Technology"]


def _ocr_noise(text: str) -> str:
    """OCR mistakes: a few swapped letters, missing spaces and stray marks."""
    out = []
    for ch in text:
        r = rng.random()
        if r < 0.02 and ch.isalpha():
            out.append(rng.choice("lI1|0O"))
        elif r < 0.03 and ch == " ":
            continue
        else:
            out.append(ch)
    if rng.random() < 0.5:
        out.append(rng.choice([" ~", " .", " |", " ‘", ""]))
    return "".join(out)


def make_documents(per_type: int = 30) -> list[dict]:
    rows = []
    for doc_type, templates in DOC_TEMPLATES.items():
        for i in range(per_type):
            t = templates[i % len(templates)]
            text = t.format(name=rng.choice(NAMES), dob=f"{rng.randint(1, 28):02d}/{rng.randint(1, 12):02d}/{rng.randint(1998, 2008)}",
                            gender=rng.choice(["Male", "Female", "MALE", "FEMALE"]), d4=rng.randint(1000, 9999),
                            year=rng.randint(2000, 2026), state=rng.choice(STATES), inc=f"{rng.randint(50, 800)},000",
                            num=f"{rng.choice('ABCKMR')}{rng.randint(100000, 999999)}", date=f"{rng.randint(1, 28)}-{rng.randint(1, 12)}-{rng.randint(2022, 2026)}",
                            caste=rng.choice(["Kurmi", "Yadav", "Valmiki", "Gond", "Ezhava"]), cat=rng.choice(["OBC", "SC", "ST"]),
                            yrs=rng.randint(5, 20), pct=rng.randint(40, 90), m1=rng.randint(40, 99), m2=rng.randint(40, 99),
                            m3=rng.randint(40, 99), sgpa=f"{rng.uniform(6, 9.8):.2f}", fee=f"{rng.randint(10, 150)},000",
                            college=rng.choice(COLLEGES))
            rows.append({"text": _ocr_noise(text), "type": doc_type})
    rng.shuffle(rows)
    return rows


# ── 5. Skill extractor test set (hand-written resumes with typos) ────

SKILL_EVAL = [
    {"text": "Skills: Pyhton, SQL, MS Excel. Built dashboards in Power BI.", "skills": ["Python", "SQL", "Excel", "Power BI"]},
    {"text": "Projects: E-commerce site with React js, Node, MongoDB and Express", "skills": ["React", "Node.js", "MongoDB", "Express"]},
    {"text": "Experience: Accountant at XYZ. Tally ERP, GST filing, MS Office.", "skills": ["Tally", "GST", "MS Office", "Accounting"]},
    {"text": "Technical skills - Java, Springboot, MySQL, Git, Docker", "skills": ["Java", "Spring Boot", "MySQL", "Git", "Docker"]},
    {"text": "Tools: Figma, Adobe Photoshop, Canva. UI/UX design of a food app.", "skills": ["Figma", "Photoshop", "Canva", "UI/UX Design"]},
    {"text": "Machine Learning project with scikit learn, pandas and numpy in Python", "skills": ["Machine Learning", "scikit-learn", "Pandas", "NumPy", "Python"]},
    {"text": "Linux, Bash scripting, AWS EC2, Kubernets, CI/CD with Jenkins", "skills": ["Linux", "Bash", "AWS", "Kubernetes", "CI/CD"]},
    {"text": "Javascrpt, HTML5, CSS3, Tailwind", "skills": ["JavaScript", "HTML", "CSS", "Tailwind CSS"]},
    {"text": "Communication, Sales, CRM software, negotiation with dealers", "skills": ["Communication", "Sales", "CRM", "Negotiation"]},
    {"text": "Android app in Kotlin with REST APIs and Firebase", "skills": ["Android", "Kotlin", "REST APIs"]},
    {"text": "Taught maths to class 8 students; lesson planning and English", "skills": ["Teaching", "Lesson Planning", "English"]},
    {"text": "Data analysis in Excel, statistics, Tableau dashboards", "skills": ["Data Analysis", "Excel", "Statistics", "Tableau"]},
    {"text": "Flutter and Dart mobile app; Git for version control", "skills": ["Flutter", "Dart", "Git"]},
    {"text": "Content writing, SEO blogs, digital marketing campaigns", "skills": ["Content Writing", "Digital Marketing"]},
    {"text": "C++ data structures and algorithms practice on LeetCode", "skills": ["C++", "Data Structures", "Algorithms"]},
    {"text": "Django REST framework backend with PostgreSQL", "skills": ["Django", "PostgreSQL"]},
    {"text": "Selenium testing, manual testing, Agile scrum", "skills": ["Testing", "Agile"]},
    {"text": "AutoCAD drawings, MATLAB simulations, SolidWorks models", "skills": ["AutoCAD", "MATLAB", "SolidWorks"]},
    {"text": "Patient care and nursing in ICU, Hindi and English", "skills": ["Patient Care", "Nursing", "Hindi", "English"]},
    {"text": "Typescipt, Angular, Next.js and GraphQL", "skills": ["TypeScript", "Angular", "Next.js", "GraphQL"]},
]

# ── 6. Search test queries (scheme id that must be in the top 5) ─────

SEARCH_EVAL = [
    ("scholarship for SC students after class 10", "nsp-post-matric-sc"), ("OBC post matric scholarship", "nsp-post-matric-obc"),
    ("money for backward class students in class 9", "pm-yasasvi"), ("science degree scholarship for toppers", "inspire-she"),
    ("Karnataka state scholarship for college students", "cm-vidyasiri-karnataka"), ("scholarship for girls in engineering", "aicte-pragati-girls"),
    ("support for students with a disability", "swami-vivekananda-disability"), ("merit scholarship for top 12th marks", "central-sector-merit"),
    ("free skill training with stipend", "pmkvy-skill"), ("funding for my startup idea", "startup-india-seed"),
    ("dalit students fees help", "nsp-post-matric-sc"), ("OBC fees reimbursement college", "nsp-post-matric-obc"),
    ("YASASVI", "pm-yasasvi"), ("INSPIRE SHE", "inspire-she"), ("Vidyasiri", "cm-vidyasiri-karnataka"),
    ("AICTE girls technical education", "aicte-pragati-girls"), ("divyang scholarship", "swami-vivekananda-disability"),
    ("central sector scholarship", "central-sector-merit"), ("Kaushal Vikas", "pmkvy-skill"), ("seed fund for entrepreneurs", "startup-india-seed"),
    ("BSc physics scholarship", "inspire-she"), ("diploma girl student scholarship", "aicte-pragati-girls"),
    ("learn a trade and get placement", "pmkvy-skill"), ("prototype grant for a new business", "startup-india-seed"),
    ("hostel and food help for Karnataka students", "cm-vidyasiri-karnataka"), ("scheduled caste scholarship", "nsp-post-matric-sc"),
    ("physically challenged students money", "swami-vivekananda-disability"), ("top rank in class 12 scholarship", "central-sector-merit"),
    ("EBC DNT students scholarship", "pm-yasasvi"), ("job training scheme government", "pmkvy-skill"),
]


def _write_csv(name: str, rows: list[dict]) -> None:
    with open(DATA / name, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"  {name}: {len(rows)} rows")


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    print("Building seed datasets in", DATA)
    _write_csv("role_jobs.csv", make_role_jobs())
    _write_csv("fit_pairs.csv", make_fit_pairs())
    _write_csv("intents.csv", make_intents())
    _write_csv("documents.csv", make_documents())
    (DATA / "skill_eval.json").write_text(json.dumps(SKILL_EVAL, indent=1, ensure_ascii=False), encoding="utf-8")
    (DATA / "search_eval.json").write_text(json.dumps([{"query": q, "expect": e} for q, e in SEARCH_EVAL], indent=1), encoding="utf-8")
    print(f"  skill_eval.json: {len(SKILL_EVAL)} resumes; search_eval.json: {len(SEARCH_EVAL)} queries")


if __name__ == "__main__":
    main()
