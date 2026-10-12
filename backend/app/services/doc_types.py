"""One name per kind of document.

Schemes word the same document differently ("Income certificate (< ₹2.5 lakh)",
"Family income certificate (< ₹8 lakh)"). The planner, the knowledge graph and
the document scanner need to know these are the same document, so each name
is mapped to a type. The first eight types are the ones the document-type
classifier (app/ml) can recognise in a scan.
"""
from __future__ import annotations

import re

DOC_TYPES: list[tuple[str, str, str, float]] = [
    # (type, label, pattern, hours to get it if you do not have it)
    ("aadhaar", "Aadhaar card", r"aadhaar|aadhar|\buid\b", 2),
    ("income", "Income certificate", r"income certificate|income proof|family income", 6),
    ("caste", "Caste certificate", r"caste|\bobc\b|\bsc\b|\bst\b|tribe|community certificate|ebc|dnt", 6),
    ("domicile", "Domicile certificate", r"domicile|residence|resident", 5),
    ("disability", "Disability certificate", r"disabilit|udid|divyang|handicap", 8),
    ("marksheet", "Mark sheet", r"mark ?sheet|marks|result|grade card|percentile|transcript", 1),
    ("bank_passbook", "Bank passbook", r"bank|passbook|account", 1),
    ("fee_receipt", "Fee receipt", r"fee receipt|fee|tuition", 1),
    ("admission", "Admission proof", r"admission|bonafide|enrol|college id|institution", 2),
    ("photo", "Passport-size photo", r"photo", 0.5),
    ("startup", "Startup registration", r"dpiit|incorporation|startup|company", 10),
    ("business_plan", "Business plan / pitch deck", r"pitch|business plan", 6),
    ("id_proof", "Identity proof", r"identity|\bpan\b|voter", 2),
]
_COMPILED = [(k, label, re.compile(p, re.IGNORECASE), h) for k, label, p, h in DOC_TYPES]
LABELS = {k: label for k, label, _p, _h in DOC_TYPES}
HOURS = {k: h for k, _l, _p, h in DOC_TYPES}


def doc_type(name: str) -> str:
    """The type of a document name; unknown names get a key of their own."""
    for key, _label, pattern, _h in _COMPILED:
        if pattern.search(name or ""):
            return key
    return "other:" + re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")[:40]


def label_of(key: str, fallback: str = "") -> str:
    return LABELS.get(key) or fallback or key.split(":", 1)[-1].replace("-", " ").capitalize()


def hours_of(key: str) -> float:
    return HOURS.get(key, 2)


def owned_types(names: list[str] | None) -> set[str]:
    """Types of the documents the user said they have (names as the browser stores them)."""
    return {doc_type(n) for n in names or [] if n}
