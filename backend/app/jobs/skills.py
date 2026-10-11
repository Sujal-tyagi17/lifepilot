"""Skill dictionary and word-boundary skill extraction.

Replaces the old substring matching, where "ai" matched "maintain" and "go"
matched "good". Each canonical skill has aliases; an alias starting with "="
is matched case-sensitively (used for short or ambiguous words such as Go, R,
C, AI, ML, Excel).

Phase 2 grows this into a ~600-skill dictionary with strengths and
prerequisites; the matching rules here stay the same.
"""
from __future__ import annotations

import re
from functools import lru_cache

SKILLS: dict[str, list[str]] = {
    # Programming languages
    "Python": ["python"],
    "Java": ["java"],
    "JavaScript": ["javascript", "=JS", "ecmascript"],
    "TypeScript": ["typescript", "=TS"],
    "C": ["=C"],
    "C++": ["c++", "cpp"],
    "C#": ["c#", "csharp"],
    "Go": ["golang", "=Go"],
    "Rust": ["rust"],
    "Kotlin": ["kotlin"],
    "Swift": ["swift"],
    "PHP": ["php"],
    "Ruby": ["ruby"],
    "R": ["=R"],
    "Scala": ["scala"],
    "Dart": ["dart"],
    "Bash": ["bash", "shell scripting"],
    # Web and mobile
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3"],
    "React": ["react", "react.js", "reactjs"],
    "React Native": ["react native"],
    "Angular": ["angular", "angularjs"],
    "Vue": ["vue", "vue.js", "vuejs"],
    "Next.js": ["next.js", "nextjs"],
    "Node.js": ["node.js", "nodejs", "=Node"],
    "Express": ["express.js", "expressjs"],
    "Django": ["django"],
    "Flask": ["flask"],
    "FastAPI": ["fastapi"],
    "Spring Boot": ["spring boot", "springboot"],
    ".NET": [".net", "dotnet", "asp.net"],
    "Flutter": ["flutter"],
    "Android": ["android"],
    "iOS": ["=iOS"],
    "Tailwind CSS": ["tailwind", "tailwindcss"],
    "REST APIs": ["rest api", "rest apis", "restful", "=REST"],
    "GraphQL": ["graphql"],
    # Data and AI
    "SQL": ["sql", "=SQL"],
    "MySQL": ["mysql"],
    "PostgreSQL": ["postgresql", "postgres"],
    "MongoDB": ["mongodb", "mongo"],
    "Redis": ["redis"],
    "Kafka": ["kafka"],
    "Pandas": ["pandas"],
    "NumPy": ["numpy"],
    "scikit-learn": ["scikit-learn", "sklearn", "scikit learn"],
    "TensorFlow": ["tensorflow"],
    "PyTorch": ["pytorch"],
    "Machine Learning": ["machine learning", "=ML"],
    "Deep Learning": ["deep learning"],
    "Artificial Intelligence": ["artificial intelligence", "=AI"],
    "NLP": ["natural language processing", "=NLP"],
    "Computer Vision": ["computer vision", "opencv"],
    "Data Analysis": ["data analysis", "data analytics"],
    "Statistics": ["statistics", "statistical"],
    "Power BI": ["power bi", "powerbi"],
    "Tableau": ["tableau"],
    "Excel": ["=Excel", "ms excel", "microsoft excel", "advanced excel"],
    "Spark": ["apache spark", "pyspark", "=Spark"],
    # Cloud and DevOps
    "AWS": ["=AWS", "amazon web services"],
    "Azure": ["azure"],
    "Google Cloud": ["google cloud", "=GCP"],
    "Docker": ["docker"],
    "Kubernetes": ["kubernetes", "k8s"],
    "Linux": ["linux", "unix"],
    "Git": ["=Git", "github", "gitlab"],
    "CI/CD": ["ci/cd", "continuous integration", "jenkins", "github actions"],
    "Terraform": ["terraform"],
    "Networking": ["networking", "tcp/ip"],
    "Cybersecurity": ["cybersecurity", "cyber security", "information security"],
    # Engineering practice
    "Data Structures": ["data structures", "dsa"],
    "Algorithms": ["algorithms"],
    "System Design": ["system design"],
    "Microservices": ["microservices", "micro-services"],
    "Testing": ["unit testing", "test automation", "selenium", "pytest", "junit"],
    "Agile": ["agile", "scrum"],
    # Design
    "Figma": ["figma"],
    "UI/UX Design": ["ui/ux", "ux design", "ui design", "user experience"],
    "Photoshop": ["photoshop"],
    "Illustrator": ["illustrator"],
    "Canva": ["canva"],
    "AutoCAD": ["autocad"],
    "SolidWorks": ["solidworks"],
    "MATLAB": ["matlab"],
    # Business, finance, operations
    "Accounting": ["accounting", "bookkeeping"],
    "Tally": ["tally", "tally erp"],
    "GST": ["=GST"],
    "Taxation": ["taxation", "income tax"],
    "Financial Analysis": ["financial analysis", "financial modelling", "financial modeling"],
    "Auditing": ["auditing", "audit"],
    "Sales": ["sales"],
    "Marketing": ["marketing"],
    "Digital Marketing": ["digital marketing", "=SEO", "=SEM", "social media marketing"],
    "Content Writing": ["content writing", "copywriting"],
    "Customer Service": ["customer service", "customer support"],
    "Communication": ["communication skills", "verbal communication", "written communication"],
    "MS Office": ["ms office", "microsoft office", "ms word", "powerpoint"],
    "Project Management": ["project management", "=PMP"],
    "Operations": ["operations management", "supply chain", "logistics management"],
    "HR": ["human resources", "recruitment", "talent acquisition"],
    "Teaching": ["teaching", "tutoring"],
    "Lesson Planning": ["lesson planning", "lesson plans", "lesson plan"],
    "Patient Care": ["patient care", "patient handling", "bedside care"],
    "CRM": ["=CRM", "salesforce", "zoho crm", "hubspot"],
    "Negotiation": ["negotiation", "negotiating"],
    "Inventory Management": ["inventory management", "inventory control", "stock management"],
    "Video Editing": ["video editing", "premiere pro", "after effects", "davinci resolve"],
    "Nursing": ["nursing"],
    "Data Entry": ["data entry"],
    "English": ["=English"],
    "Hindi": ["=Hindi"],
}


def _alias_pattern(alias: str) -> re.Pattern[str]:
    case_sensitive = alias.startswith("=")
    word = alias[1:] if case_sensitive else alias
    # Boundaries: not preceded/followed by letters, digits or the symbols that
    # are part of skill names (+, #, .) so "C" never matches inside "C++".
    pattern = rf"(?<![A-Za-z0-9+#.]){re.escape(word)}(?![A-Za-z0-9+#])"
    if word in ("C", "R"):
        # "C" or "R" followed by "-", "&" or "/" is usually not the language (C-suite, R&D, C/O)
        pattern = rf"(?<![A-Za-z0-9+#.]){word}(?![A-Za-z0-9+#&/\-])"
    if word == "Go":
        # "Go" the language, not "go to", "go ahead", "Go-live"
        pattern = r"(?<![A-Za-z0-9])Go(?![A-Za-z0-9\-])(?!\s+(?:to|ahead|through|beyond|live)\b)"
    return re.compile(pattern, 0 if case_sensitive else re.IGNORECASE)


@lru_cache(maxsize=1)
def _compiled() -> list[tuple[str, list[re.Pattern[str]]]]:
    return [(name, [_alias_pattern(a) for a in aliases]) for name, aliases in SKILLS.items()]


def canonical(skill: str) -> str | None:
    """Map a user-typed skill ("reactjs", "ML") to its canonical name, if known."""
    s = skill.strip()
    if not s:
        return None
    for name, aliases in SKILLS.items():
        if s.lower() == name.lower():
            return name
        # A skill the user typed on purpose: case does not matter ("ml" = ML)
        if any(s.lower() == a.lstrip("=").lower() for a in aliases):
            return name
    return None


def extract_skills(text: str | None) -> list[str]:
    """Canonical skills mentioned in `text`, in order of first appearance."""
    if not text:
        return []
    found: list[tuple[int, str]] = []
    for name, patterns in _compiled():
        positions = [m.start() for p in patterns if (m := p.search(text))]
        if positions:
            found.append((min(positions), name))
    # "React Native" also contains "React"; keep both only if React appears on its own too
    names = [n for _, n in sorted(found)]
    if "React Native" in names and "React" in names:
        standalone = re.search(r"(?i)(?<![A-Za-z])react(?!\s+native)(?![A-Za-z])", text)
        if not standalone:
            names.remove("React")
    return names


def normalise_user_skills(skills: list[str] | None) -> list[str]:
    """Canonicalise skills the user typed; unknown skills are kept as typed."""
    out: list[str] = []
    for s in skills or []:
        c = canonical(s) or s.strip()
        if c and c.lower() not in {o.lower() for o in out}:
            out.append(c)
    return out


# ── Fuzzy matching for typos ("Pyhton", "Javascrpt", "Kubernets") ──

@lru_cache(maxsize=1)
def _fuzzy_aliases() -> list[tuple[str, str]]:
    """(alias, skill) pairs long enough to fuzzy-match safely: single words of 6+ letters."""
    out = []
    for name, aliases in SKILLS.items():
        for a in [name, *aliases]:
            a = a.lstrip("=").lower()
            if len(a) >= 6 and a.isalpha():
                out.append((a, name))
    return out


def fuzzy_skills(text: str | None, already: list[str] | None = None, threshold: float = 0.8) -> list[str]:
    """Skills written with a small typo. Each word of 6+ letters is compared with
    every alias; a match needs the same first letter, a length within 2, and a
    similarity of at least `threshold` (difflib ratio)."""
    from difflib import SequenceMatcher

    if not text:
        return []
    have = set(already or [])
    found: list[str] = []
    for word in dict.fromkeys(re.findall(r"[A-Za-z]{6,}", text)):
        w = word.lower()
        best, best_score = None, threshold
        for alias, name in _fuzzy_aliases():
            # skip inflections of ordinary words: "expressed" is not Express
            if alias[0] != w[0] or abs(len(alias) - len(w)) > 2 or alias == w or w.startswith(alias):
                continue
            score = SequenceMatcher(None, w, alias).ratio()
            if score >= best_score:
                best, best_score = name, score
        if best and best not in have and best not in found:
            found.append(best)
    return found


def extract_skills_fuzzy(text: str | None) -> list[str]:
    """Exact matches first, then typo matches."""
    exact = extract_skills(text)
    return exact + fuzzy_skills(text, exact)
