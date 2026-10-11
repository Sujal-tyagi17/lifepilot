"""RAG (Retrieval-Augmented Generation) pipeline.

Retrieves relevant scheme context from ChromaDB, augments the user's
question with that context, and sends it to the LLM for a grounded answer.
"""
from __future__ import annotations

import logging

from app.knowledge.vectorstore import search as vector_search
from datetime import date

from app.llm.provider import clean_reply, get_provider

logger = logging.getLogger("lifepilot.knowledge.rag")

SYSTEM = """You are LifePilot's assistant for Indian students and citizens. You answer questions about
government schemes, scholarships, documents and deadlines using ONLY the facts you are given.

How to answer:
- Answer the question in the first line. No greeting, no preamble, no restating the question.
- Then short bullet points, one per scheme: **Scheme name**: amount · deadline (days left) · one key detail.
- Mention only schemes in the facts. Never invent schemes, amounts, dates or links.
- "Eligible" schemes are ones the person qualifies for. Say clearly when a scheme is only a partial match and what is missing.
- If the facts do not cover the question, say so in one line and suggest what they can do.
- At most about 120 words. End with one clear next step.
- Reply in the same language as the question (Hindi if they write in Hindi)."""

_PROMPT = """FACTS

Person: {profile_summary}
Today: {today}

Schemes they are ELIGIBLE for (open):
{eligible}

Partial matches (not eligible yet):
{partial}
{extra}
{chat_history_section}
QUESTION ({intent}): {question}"""


def _is_open_eligible(m: dict) -> bool:
    """Eligible and still accepting applications (older saved runs lack status)."""
    status = m.get("status") or ("eligible" if m.get("eligible") else "partial")
    return status == "eligible"


def _days_left(deadline: str | None) -> int | None:
    try:
        return (date.fromisoformat(deadline or "") - date.today()).days
    except ValueError:
        return None


def _when(m: dict) -> str:
    d = _days_left(m.get("deadline"))
    if d is None:
        return "deadline: check the portal"
    return f"deadline {m['deadline']} ({d} days left)" if d >= 0 else f"closed on {m['deadline']}"


def _scheme_line(m: dict, with_docs: bool = True) -> str:
    parts = [f"- {m['title']}: {m.get('amount') or 'amount not stated'}; {_when(m)}"]
    if m.get("url"):
        parts.append(f"apply: {m['url']}")
    if with_docs and m.get("documents"):
        parts.append("documents: " + ", ".join(m["documents"][:6]))
    if m.get("reasons"):
        parts.append("why: " + "; ".join(m["reasons"][:2]))
    return "; ".join(parts)


def rag_answer(
    question: str,
    matches: list[dict] | None = None,
    profile: dict | None = None,
    chat_history: str | None = None,
) -> str:
    """Answer a question from the person's own matches (plus the scheme database for other schemes)."""
    llm = get_provider()
    matches = matches or []
    intent = detect_intent(question)["label"]
    eligible = [m for m in matches if _is_open_eligible(m)]
    partial = [m for m in matches if not _is_open_eligible(m) and m.get("status") != "closed"]

    # Schemes from the database that are not among their matches, for questions about a named scheme
    known = {m.get("title") for m in matches}
    try:
        others = [d for d in vector_search(question, n_results=3) if d.get("title") not in known]
    except Exception:
        others = []
    extra = ""
    if others:
        extra = "\nOther schemes in the database (NOT checked for this person):\n" + "\n".join(
            f"- {d.get('title')}: {d.get('amount', 'N/A')}; deadline {d.get('deadline', 'N/A')}" for d in others)

    profile_summary = "No profile available."
    if profile:
        parts = [f"{k}: {profile[k]}" for k in ("name", "category", "state", "education_level") if profile.get(k)]
        if profile.get("annual_income"):
            parts.append(f"family income: ₹{profile['annual_income']:,}/year")
        profile_summary = ", ".join(parts) or "Incomplete profile."

    prompt = _PROMPT.format(
        profile_summary=profile_summary,
        today=date.today().isoformat(),
        eligible="\n".join(_scheme_line(m) for m in eligible[:8]) or "- none yet",
        partial="\n".join(f"- {m['title']}: missing: {'; '.join(m.get('unmet') or ['some criteria'])[:160]}" for m in partial[:5]) or "- none",
        extra=extra,
        chat_history_section=f"\nEarlier in this chat:\n{chat_history}\n" if chat_history else "",
        question=question,
        intent=intent.replace("_", " "),
    )

    if llm.name != "mock":
        try:
            reply = clean_reply(llm.generate(prompt, system=SYSTEM))
            # A real answer, not an echo of our own instructions
            if reply and len(reply) > 20 and "FACTS" not in reply[:200] and "QUESTION:" not in reply:
                return reply
        except Exception as e:
            logger.warning(f"RAG LLM call failed: {e}")

    return _offline_answer(question, matches, profile, intent)


# Words in many scheme names; they don't pick out one scheme
_GENERIC = {"scheme", "schemes", "scholarship", "scholarships", "students", "student", "india", "indian", "national",
            "central", "sector", "girls", "yojana", "grant", "grants", "merit", "matric", "post-matric", "science",
            "training", "skill", "stipend", "pradhan", "mantri", "state", "government", "fund", "support"}


_KEYWORDS = {
    "eligibility": ("eligible", "qualify", "can i get", "which scheme", "schemes for me", "my schemes", "पात्र", "योग्य"),
    "documents": ("document", "papers", "checklist", "certificate", "दस्तावेज", "कागज"),
    "deadlines": ("deadline", "last date", "when", "closing", "तारीख", "तिथि"),
    "benefits": ("how much", "benefit", "money", "amount", "राशि", "पैसे"),
    "how_to_apply": ("how do i apply", "how to apply", "where do i apply", "apply link", "process", "आवेदन कैसे"),
    "jobs": ("job", "career", "internship", "नौकरी"),
}


def detect_intent(question: str) -> dict:
    """What the question is about: the trained intent classifier (app/ml), or keywords if it is not sure."""
    from app.ml.predict import intent as ml_intent
    r = ml_intent(question)
    if r and r["confidence"] >= 0.4:
        return {"label": r["label"], "confidence": r["confidence"], "by": "model"}
    q = question.lower()
    for label, words in _KEYWORDS.items():
        if any(w in q for w in words):
            return {"label": label, "confidence": None, "by": "keywords"}
    return {"label": "other", "confidence": r["confidence"] if r else None, "by": "model" if r else "keywords"}


def _named_scheme(q: str, matches: list[dict]) -> dict | None:
    for m in matches:
        title = m.get("title", "").lower()
        keywords = [w for w in title.replace("-", " ").replace("(", " ").replace(")", " ").split()
                    if len(w) > 4 and w not in _GENERIC]
        if any(kw in q for kw in keywords) or title in q:
            return m
    return None


def _offline_answer(question: str, matches: list[dict], profile: dict | None, intent: str | None = None) -> str:
    """Answer without an LLM, routed by the question's intent."""
    q = question.lower()
    intent = intent or detect_intent(question)["label"]
    eligible = [m for m in matches if _is_open_eligible(m)]

    named = _named_scheme(q, matches)
    if named and intent in ("eligibility", "documents", "deadlines"):
        t = named["title"]
        if intent == "eligibility":
            if _is_open_eligible(named):
                why = "; ".join(named.get("reasons") or [])[:300]
                return f"Yes, you qualify for **{t}**" + (f": {why}." if why else ".") + f"\n\n**Next step:** {_when(named)}" + (f", apply at {named['url']}." if named.get("url") else ".")
            missing = "; ".join(named.get("unmet") or ["some criteria"])
            return f"Not yet for **{t}**. Missing: {missing}.\n\nOpen **Schemes → What if** to see what would change it."
        if intent == "documents":
            docs = named.get("documents") or []
            return (f"Documents for **{t}**:\n" + "\n".join(f"• {d}" for d in docs)) if docs else f"The portal for **{t}** lists its documents; none are recorded here."
        return f"**{t}**: {_when(named)}" + (f". Apply at {named['url']}." if named.get("url") else ".")

    if named:  # about one scheme by name: where and how to apply, and what it gives
        m = named
        title = m.get("title", "").lower()
        if title:
            # Special case for Pragati Scholarship
            if "pragati" in title:
                return (
                    "Regarding the **AICTE Pragati Scholarship for Girls**:\n\n"
                    "• **Where to apply**: While AICTE publishes the guidelines, applications must be submitted on the **National Scholarship Portal (NSP)** at https://scholarships.gov.in/.\n"
                    "• **Where to find it on the AICTE website**: On the AICTE portal, it is located under the **Student Development Schemes** tab in the left-hand menu. However, there is no direct application button there; applications are processed entirely through the NSP portal.\n"
                    "• **Benefits**: ₹50,000/year + ₹10,000 contingency.\n"
                    "• **Link**: [Apply on National Scholarship Portal](https://scholarships.gov.in/)"
                )
            # Special case for Yasasvi Scholarship
            if "yasasvi" in title:
                return (
                    "Regarding the **PM YASASVI Scholarship (OBC/EBC/DNT)**:\n\n"
                    "• **Where to apply**: Although the National Testing Agency (NTA) formerly hosted registrations at `yet.nta.ac.in`, registrations are now fully integrated and processed on the **National Scholarship Portal (NSP)** at https://scholarships.gov.in/.\n"
                    "• **Benefits**: ₹75,000 to ₹1,25,000 / year.\n"
                    "• **Link**: [Apply on National Scholarship Portal](https://scholarships.gov.in/)"
                )
            # General case
            provider = m.get("provider", "the government")
            url = m.get("url", "")
            amount = m.get("amount", "TBD")
            ans = f"Here is what I found for **{m.get('title')}**:\n\n"
            if provider:
                ans += f"• **Provider**: {provider}\n"
            if amount:
                ans += f"• **Benefits**: {amount}\n"
            if url:
                ans += f"• **Where to apply**: You can submit your application on the official portal here: {url}\n"
            return ans

    if intent == "eligibility":
        if eligible:
            ordered = sorted(eligible, key=lambda m: (_days_left(m.get("deadline")) is None, _days_left(m.get("deadline")) or 0))
            lines = [f"You qualify for **{len(eligible)} scheme{'s' if len(eligible) != 1 else ''}**:", ""]
            for m in ordered[:6]:
                lines.append(f"• **{m['title']}**: {m.get('amount') or 'amount not stated'} · {_when(m)}")
            first = ordered[0]
            lines += ["", f"**Next step:** apply for {first['title']} first"
                      + (f" ({_days_left(first.get('deadline'))} days left)" if _days_left(first.get("deadline")) is not None else "")
                      + (f" at {first['url']}" if first.get("url") else "") + "."]
            return "\n".join(lines)
        return "You don't fully qualify for any scheme yet. Open **Schemes** to see what is missing for each partial match, or update your profile."

    if intent == "documents":
        with_docs = [m for m in eligible if m.get("documents")]
        if not with_docs:
            return "No documents to prepare yet: you don't fully qualify for any scheme. Open **Schemes** to see what is missing."
        common: dict[str, int] = {}
        for m in with_docs:
            for d in m["documents"]:
                common[d] = common.get(d, 0) + 1
        shared = [d for d, n in common.items() if n > 1]
        lines = ["Documents for the schemes you qualify for:", ""]
        if shared:
            lines += ["**Needed for more than one scheme:** " + ", ".join(sorted(shared)), ""]
        for m in with_docs[:5]:
            own = [d for d in m["documents"] if d not in shared]
            if own:
                lines.append(f"• **{m['title']}**: " + ", ".join(own))
        lines += ["", "**Next step:** keep scanned copies in **Documents** so they are ready when you apply."]
        return "\n".join(lines)

    if intent == "deadlines":
        dated = sorted(((d, m) for m in eligible if (d := _days_left(m.get("deadline"))) is not None and d >= 0),
                       key=lambda t: t[0])
        if not dated:
            return "None of the schemes you qualify for has a fixed deadline right now. Check each portal for dates."
        lines = ["Next deadlines for schemes you qualify for:", ""]
        for d, m in dated[:5]:
            urgent = " ⚠️" if d <= 7 else ""
            lines.append(f"• **{m['title']}**: {m['deadline']} ({d} day{'s' if d != 1 else ''} left){urgent}")
        d, m = dated[0]
        lines += ["", f"**Next step:** finish {m['title']} first" + (f" at {m['url']}" if m.get("url") else "") + "."]
        return "\n".join(lines)

    if intent == "benefits" and eligible:
        lines = [f"What the {len(eligible)} scheme{'s' if len(eligible) != 1 else ''} you qualify for give:", ""]
        for m in eligible[:6]:
            lines.append(f"• **{m['title']}**: {m.get('amount') or 'varies'}")
        lines += ["", "**Next step:** the Home page shows the total value and what to do first."]
        return "\n".join(lines)

    if intent == "how_to_apply":
        with_links = [m for m in eligible if m.get("url")]
        lines = ["Most scholarships are applied for online on the **National Scholarship Portal** (https://scholarships.gov.in/): "
                 "register with your mobile number, fill the form, upload documents, then your college verifies it.", ""]
        if with_links:
            lines.append("Apply links for the schemes you qualify for:")
            lines += [f"• **{m['title']}**: {m['url']}" for m in with_links[:5]]
        lines += ["", "**Next step:** keep your documents ready in **Documents** before you start the form."]
        return "\n".join(lines)

    if intent == "jobs":
        return ("For jobs, open the **Jobs** page: add your resume (or pick your experience), and you get matched openings "
                "with a fit score, the skills to learn, and a week-by-week plan for any job you pick.")

    return (
        f"You qualify for {len(eligible)} scheme{'s' if len(eligible) != 1 else ''} and partly match "
        f"{len(matches) - len(eligible)} more. Ask me which ones you qualify for, the documents you need, "
        f"the next deadlines, or about a scheme by name."
    )
