"""Where a job is, and how close that is to the user.

Job sources write locations in many ways ("Bengaluru, Karnataka", "Bangalore
Urban", "Gurgaon", "Remote", "Work from home"). We map them to a state so jobs
in the user's own state can be shown first, then remote jobs, then the rest of
India.
"""
from __future__ import annotations

import re

# State -> major cities and common spellings (lower case).
STATE_CITIES: dict[str, list[str]] = {
    "Andhra Pradesh": ["visakhapatnam", "vizag", "vijayawada", "guntur", "tirupati", "nellore", "kakinada", "amaravati"],
    "Arunachal Pradesh": ["itanagar"],
    "Assam": ["guwahati", "dibrugarh", "silchar", "jorhat"],
    "Bihar": ["patna", "gaya", "muzaffarpur", "bhagalpur"],
    "Chhattisgarh": ["raipur", "bhilai", "bilaspur", "durg"],
    "Goa": ["panaji", "panjim", "margao", "vasco da gama"],
    "Gujarat": ["ahmedabad", "surat", "vadodara", "baroda", "rajkot", "gandhinagar", "gift city", "bhavnagar"],
    "Haryana": ["gurugram", "gurgaon", "faridabad", "panipat", "ambala", "karnal", "sonipat", "hisar"],
    "Himachal Pradesh": ["shimla", "dharamshala", "solan", "mandi", "baddi"],
    "Jharkhand": ["ranchi", "jamshedpur", "dhanbad", "bokaro"],
    "Karnataka": ["bengaluru", "bangalore", "mysuru", "mysore", "mangaluru", "mangalore", "hubli", "hubballi", "belagavi", "belgaum", "dharwad"],
    "Kerala": ["kochi", "cochin", "thiruvananthapuram", "trivandrum", "kozhikode", "calicut", "thrissur", "kollam"],
    "Madhya Pradesh": ["indore", "bhopal", "jabalpur", "gwalior", "ujjain"],
    "Maharashtra": ["mumbai", "bombay", "pune", "nagpur", "nashik", "thane", "navi mumbai", "aurangabad", "kolhapur", "solapur"],
    "Manipur": ["imphal"],
    "Meghalaya": ["shillong"],
    "Mizoram": ["aizawl"],
    "Nagaland": ["kohima", "dimapur"],
    "Odisha": ["bhubaneswar", "cuttack", "rourkela", "puri"],
    "Punjab": ["ludhiana", "amritsar", "jalandhar", "patiala", "mohali", "bathinda"],
    "Rajasthan": ["jaipur", "jodhpur", "udaipur", "kota", "ajmer", "bikaner"],
    "Sikkim": ["gangtok"],
    "Tamil Nadu": ["chennai", "madras", "coimbatore", "madurai", "tiruchirappalli", "trichy", "salem", "hosur", "vellore"],
    "Telangana": ["hyderabad", "secunderabad", "warangal", "karimnagar"],
    "Tripura": ["agartala"],
    "Uttar Pradesh": ["noida", "greater noida", "ghaziabad", "lucknow", "kanpur", "agra", "varanasi", "prayagraj", "allahabad", "meerut"],
    "Uttarakhand": ["dehradun", "haridwar", "roorkee", "haldwani"],
    "West Bengal": ["kolkata", "calcutta", "howrah", "durgapur", "siliguri", "salt lake"],
    "Andaman and Nicobar Islands": ["port blair"],
    "Chandigarh": ["chandigarh"],
    "Dadra and Nagar Haveli and Daman and Diu": ["daman", "silvassa"],
    "Delhi": ["new delhi", "delhi ncr", "ncr"],
    "Jammu and Kashmir": ["srinagar", "jammu"],
    "Ladakh": ["leh"],
    "Lakshadweep": ["kavaratti"],
    "Puducherry": ["pondicherry"],
}

_REMOTE = re.compile(r"\bremote\b|work from home|\bwfh\b|anywhere in india", re.IGNORECASE)


def _has(text: str, phrase: str) -> bool:
    return re.search(rf"(?<![a-z]){re.escape(phrase)}(?![a-z])", text) is not None


def find_state(text: str | None) -> str | None:
    """The Indian state a location string points to, if any."""
    low = (text or "").lower()
    if not low:
        return None
    # Full state names first ("Karnataka"), longest first so "West Bengal" wins over "Bengal"
    for state in sorted(STATE_CITIES, key=len, reverse=True):
        if _has(low, state.lower()):
            return state
    for state, cities in STATE_CITIES.items():
        if any(_has(low, c) for c in cities):
            return state
    return None


def find_place(text: str | None) -> str | None:
    """A readable place name from free text: the first city or state mentioned."""
    low = (text or "").lower()
    for state, cities in STATE_CITIES.items():
        for c in cities:
            if _has(low, c):
                return c.title() if c not in ("ncr", "delhi ncr") else "Delhi NCR"
    state = find_state(text)
    if state:
        return state
    return "Remote" if _REMOTE.search(low) else None


def is_remote(text: str | None) -> bool:
    return bool(_REMOTE.search(text or ""))


def location_rank(job: dict, user_state: str | None) -> tuple[int, str]:
    """(rank, label): 0 in your state, 1 remote, 2 elsewhere in India, 3 abroad or unknown."""
    where = " ".join(filter(None, [job.get("location"), job.get("job_type")]))
    state = find_state(where)
    if user_state and state == user_state:
        return 0, "near"
    if is_remote(where):
        return 1, "remote"
    if state or (job.get("country") or "").lower() == "india":
        return 2, "india"
    return 3, "other"
