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
QUESTION: {question}"""


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
    )

    if llm.name != "mock":
        try:
            reply = clean_reply(llm.generate(prompt, system=SYSTEM))
            # A real answer, not an echo of our own instructions
            if reply and len(reply) > 20 and "FACTS" not in reply[:200] and "QUESTION:" not in reply:
                return reply
        except Exception as e:
            logger.warning(f"RAG LLM call failed: {e}")

    return _offline_answer(question, matches, profile)


# Words in many scheme names; they don't pick out one scheme
_GENERIC = {"scheme", "schemes", "scholarship", "scholarships", "students", "student", "india", "indian", "national",
            "central", "sector", "girls", "yojana", "grant", "grants", "merit", "matric", "post-matric", "science",
            "training", "skill", "stipend", "pradhan", "mantri", "state", "government", "fund", "support"}


def _offline_answer(question: str, matches: list[dict], profile: dict | None) -> str:
    """Simple keyword-based fallback when LLM is unavailable."""
    q = question.lower()
    eligible = [m for m in matches if _is_open_eligible(m)]

    # Check if user is asking about a specific scheme (e.g. pragati, yasasvi, etc.)
    for m in matches:
        title = m.get("title", "").lower()
        # Extract keywords from title (e.g., "pragati", "yasasvi", "vidyasiri", "inspire", "vivekananda")
        keywords = [w for w in title.replace("-", " ").replace("(", " ").replace(")", " ").split()
                    if len(w) > 4 and w not in _GENERIC]
        if any(kw in q for kw in keywords) or title in q:
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

    if any(w in q for w in ("eligible", "qualify", "can i", "which scheme", "schemes for me", "my schemes")):
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

    if any(w in q for w in ("document", "papers", "checklist")):
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

    if any(w in q for w in ("deadline", "when", "date", "last date")):
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

    if any(w in q for w in ("how much", "benefit", "money", "amount")):
        if eligible:
            lines = [f"You could unlock benefits from {len(eligible)} scheme(s):"]
            for m in eligible[:5]:
                lines.append(f"• {m['title']} — {m.get('amount', 'varies')}")
            return "\n".join(lines)

    return (
        f"You qualify for {len(eligible)} scheme{'s' if len(eligible) != 1 else ''} and partly match "
        f"{len(matches) - len(eligible)} more. Ask me which ones you qualify for, the documents you need, "
        f"the next deadlines, or about a scheme by name."
    )
