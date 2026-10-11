"""Check a scanned document against the profile.

The browser reads the image with OCR (Tesseract.js) and sends only the text.
Here we:
  1. find the document type (the trained classifier in app/ml; keywords if it is not sure)
  2. pull out fields with patterns: name, issue date, amount, percentage, category, IDs
  3. check them: the name matches the profile, the income fits the profile and the
     scheme limits, the certificate is recent enough, the category matches, a
     disability is 40% or more

Limits, stated in the UI too: this checks consistency, not authenticity; it
cannot spot a forged certificate. ID numbers are masked and never stored.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from difflib import SequenceMatcher

from app.services.doc_types import LABELS, doc_type

# How long a certificate is usually accepted (days). Rules vary by state; None = no expiry.
VALIDITY = {"income": 365, "fee_receipt": 365, "disability": 5 * 365, "domicile": None, "caste": None,
            "marksheet": None, "aadhaar": None, "bank_passbook": None}

_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _dates(text: str) -> list[date]:
    out = []
    for d, m, y in re.findall(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b", text):
        try:
            out.append(date(int(y), int(m), int(d)))
        except ValueError:
            pass
    for d, mon, y in re.findall(r"\b(\d{1,2})\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?,?\s*(\d{4})\b", text, re.I):
        try:
            out.append(date(int(y), _MONTHS[mon[:3].lower()], int(d)))
        except ValueError:
            pass
    return [d for d in out if 1950 <= d.year <= date.today().year + 1]


def _amount(text: str) -> int | None:
    low = text.lower().replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(lakh|lac)", low)
    if m:
        return int(float(m.group(1)) * 100_000)
    m = re.search(r"(?:rs\.?|₹|inr|rupees)\s*(\d{4,8})", low) or re.search(r"(\d{4,8})\s*(?:rupees|/-)", low)
    return int(m.group(1)) if m else None


def _mask(text: str) -> str:
    """Hide anything that looks like an Aadhaar, account or certificate number except its last 4 digits."""
    text = re.sub(r"\b(\d{4})\s?(\d{4})\s?(\d{4})\b", lambda m: "XXXX XXXX " + m.group(3), text)
    return re.sub(r"\b(\d{5,})(\d{4})\b", lambda m: "X" * len(m.group(1)) + m.group(2), text)


def _name_score(text: str, name: str) -> float:
    """How well the profile name appears in the text (0–1), allowing for OCR mistakes."""
    words = [w for w in re.findall(r"[a-z]+", (name or "").lower()) if len(w) > 1]
    if not words:
        return 0.0
    tokens = re.findall(r"[a-z]+", text.lower())
    scores = []
    for w in words:
        best = max((SequenceMatcher(None, w, t).ratio() for t in tokens), default=0)
        scores.append(best)
    return round(sum(scores) / len(scores), 2)


def classify(text: str) -> dict:
    from app.ml.predict import document_type
    ml = document_type(text, explain_it=True)
    if ml and ml["confidence"] >= 0.5:
        return {"type": ml["label"], "confidence": ml["confidence"], "by": "model", "because": ml.get("because", [])}
    key = doc_type(text)
    if key in VALIDITY:
        return {"type": key, "confidence": None, "by": "keywords", "because": []}
    if ml:
        return {"type": ml["label"], "confidence": ml["confidence"], "by": "model", "because": ml.get("because", [])}
    return {"type": "other", "confidence": None, "by": "keywords", "because": []}


def verify(text: str, profile: dict | None = None, income_limits: list[int] | None = None) -> dict:
    profile = profile or {}
    text = re.sub(r"\s+", " ", text or "").strip()
    kind = classify(text)
    t = kind["type"]
    fields: dict = {}
    checks: list[dict] = []

    def check(name: str, ok: bool | None, message: str):
        checks.append({"check": name, "ok": ok, "message": message})

    dates = _dates(text)
    if dates:
        issued = max(d for d in dates if d <= date.today()) if any(d <= date.today() for d in dates) else None
        if issued:
            fields["issue_date"] = issued.isoformat()
    if t == "income":
        amt = _amount(text)
        if amt:
            fields["annual_income"] = amt
    if t == "marksheet":
        pct = re.search(r"(\d{2}(?:\.\d+)?)\s*%", text)
        cgpa = re.search(r"\b(?:cgpa|sgpa)\D{0,5}(\d(?:\.\d+)?)", text, re.I)
        if pct:
            fields["percentage"] = float(pct.group(1))
        elif cgpa:
            fields["cgpa"] = float(cgpa.group(1))
    if t == "caste":
        cat = re.search(r"\b(OBC|SC|ST|EWS)\b|other backward|scheduled (caste|tribe)", text, re.I)
        if cat:
            raw = cat.group(0).lower()
            fields["category"] = "OBC" if "backward" in raw else "SC" if "caste" in raw else "ST" if "tribe" in raw else cat.group(0).upper()
    if t == "disability":
        pct = re.search(r"(\d{2,3})\s*%", text)
        if pct:
            fields["disability_percent"] = int(pct.group(1))
    if t == "aadhaar":
        last4 = re.search(r"(?:\d{4}|X{4})\s?(?:\d{4}|X{4})\s?(\d{4})", text)
        if last4:
            fields["aadhaar_last4"] = last4.group(1)

    # Checks
    if profile.get("name"):
        s = _name_score(text, profile["name"])
        fields["name_match"] = s
        check("name", s >= 0.8, f"Your name ({profile['name']}) " + ("appears on it" if s >= 0.8 else
              "was not found clearly. Check the spelling matches your other documents"))
    if t in VALIDITY and VALIDITY[t] and fields.get("issue_date"):
        age = (date.today() - date.fromisoformat(fields["issue_date"])).days
        ok = age <= VALIDITY[t]
        check("validity", ok, f"Issued {fields['issue_date']}: " + ("recent enough" if ok else
              f"older than {VALIDITY[t] // 365} year{'s' if VALIDITY[t] > 365 else ''}. Many portals need a newer one"))
    if "annual_income" in fields:
        amt = fields["annual_income"]
        if profile.get("annual_income"):
            diff = abs(amt - profile["annual_income"]) / max(1, profile["annual_income"])
            check("income_matches_profile", diff <= 0.1,
                  f"Income ₹{amt:,} " + ("matches your profile" if diff <= 0.1 else
                  f"differs from your profile (₹{profile['annual_income']:,}). Use the figure on the certificate"))
        for lim in sorted(set(income_limits or [])):
            check(f"income_limit_{lim}", amt <= lim, f"₹{amt:,} is {'within' if amt <= lim else 'above'} the ₹{lim:,} limit of a scheme you are applying to")
    if "category" in fields and profile.get("category"):
        ok = fields["category"].upper() == str(profile["category"]).upper()
        check("category", ok, f"Category on it: {fields['category']}" + ("" if ok else f" (your profile says {profile['category']})"))
    if "disability_percent" in fields:
        ok = fields["disability_percent"] >= 40
        check("disability_40", ok, f"{fields['disability_percent']}% disability: " + ("meets the 40% rule" if ok else "below the 40% most schemes need"))

    problems = [c for c in checks if c["ok"] is False]
    return {
        "type": t,
        "type_label": LABELS.get(t, t.replace("_", " ").capitalize()),
        "classifier": kind,
        "fields": fields,
        "checks": checks,
        "verdict": "ok" if checks and not problems else "check" if problems else "unchecked",
        "preview": _mask(text[:400]),
        "note": "This checks that the document is consistent with your profile, not that it is genuine.",
        "checked_at": datetime.now().isoformat(timespec="seconds"),
    }
