"""Load the trained models (app/ml/models/) and make explained predictions.

Every function returns None when its model file is missing or cannot be
loaded (for example after a scikit-learn upgrade), so the app falls back to
its rules and keeps working. Run `python -m app.ml.train` to (re)build them.
"""
from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path

import numpy as np

logger = logging.getLogger("lifepilot.ml")
MODELS = Path(__file__).resolve().parent / "models"


@lru_cache(maxsize=None)
def _load(name: str):
    path = MODELS / name
    if not path.exists():
        return None
    try:
        import joblib
        return joblib.load(path)
    except Exception as e:  # missing scikit-learn, or a version that cannot read the file
        logger.warning(f"Could not load {name} ({e}); using rules. Run: python -m app.ml.train")
        return None


def reload() -> None:
    _load.cache_clear()
    fit_weights.cache_clear()
    metrics.cache_clear()


@lru_cache(maxsize=1)
def metrics() -> dict | None:
    path = MODELS / "metrics.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


@lru_cache(maxsize=1)
def fit_weights() -> dict | None:
    """Learned weights and cut-offs for the job fit score, or None."""
    path = MODELS / "fit_weights.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return data if abs(sum(data["weights"].values()) - 1) < 0.05 else None
    except (ValueError, KeyError):
        return None


def _softmax(z: np.ndarray, t: float = 1.0) -> np.ndarray:
    z = (z - z.max()) * t
    e = np.exp(z)
    return e / e.sum()


def _scores(model, text: str) -> tuple[list[str], np.ndarray]:
    """Class names and a probability-like score per class."""
    clf = model.steps[-1][1]
    if hasattr(clf, "predict_proba"):
        return list(clf.classes_), model.predict_proba([text])[0]
    # SVM margins to 0–1: a softmax with temperature 8, tuned so a clear match is ~0.9 and "Chef" stays under 0.1
    return list(clf.classes_), _softmax(model.decision_function([text])[0], t=8.0)


def explain(model, text: str, label: str, top: int = 6) -> list[dict]:
    """The words (or letter groups) in `text` that pushed the prediction towards `label` most."""
    vec, clf = model.steps[0][1], model.steps[-1][1]
    classes = [str(c) for c in clf.classes_]
    coef = clf.coef_[classes.index(label)] if clf.coef_.shape[0] > 1 else clf.coef_[0]
    if getattr(vec, "analyzer", "word") != "word":
        # Character n-gram models: score whole words, which people can read
        words = list(dict.fromkeys(w for w in re.findall(r"[\w\u0900-\u097F]+", text) if len(w) > 1))
        if not words:
            return []
        X = vec.transform(words)
        scores = X @ coef
        ranked = sorted(zip(words, scores), key=lambda p: -p[1])
        return [{"term": w, "weight": round(float(v), 3)} for w, v in ranked if v > 0][:top]
    x = vec.transform([text])
    contrib = x.multiply(coef).tocsr()
    names = vec.get_feature_names_out()
    pairs = sorted(zip(contrib.indices, contrib.data), key=lambda p: -p[1])
    out, seen = [], set()
    for i, v in pairs:
        term = names[i].strip()
        if v <= 0 or not term or term in seen:
            continue
        # character n-grams overlap a lot; keep ones that are not inside a term already shown
        if any(term in s or s in term for s in seen):
            continue
        seen.add(term)
        out.append({"term": term, "weight": round(float(v), 3)})
        if len(out) >= top:
            break
    return out


def _classify(file: str, text: str, explain_it: bool) -> dict | None:
    model = _load(file)
    if model is None or not (text or "").strip():
        return None
    if model.steps[0][1].transform([text]).nnz == 0:
        return None   # not one word the model knows: no guess at all ("Chef for an Italian restaurant")
    classes, probs = _scores(model, text)
    classes = [str(c) for c in classes]
    order = np.argsort(-probs)
    best = classes[order[0]]
    out = {"label": best, "confidence": round(float(probs[order[0]]), 3),
           "top": [{"label": classes[i], "score": round(float(probs[i]), 3)} for i in order[:3]]}
    if explain_it:
        out["because"] = explain(model, text, best)
    return out


def role_family(title: str, description: str = "") -> tuple[str, float] | None:
    r = _classify("role_family.joblib", f"{title}. {description}".strip(". "), False)
    return (r["label"], r["confidence"]) if r else None


def role_family_explained(text: str) -> dict | None:
    return _classify("role_family.joblib", text, True)


def intent(text: str, explain_it: bool = False) -> dict | None:
    return _classify("intent.joblib", text, explain_it)


def document_type(text: str, explain_it: bool = True) -> dict | None:
    return _classify("document_type.joblib", text, explain_it)


FIT_FEATURES = ["must", "nice", "role", "experience", "education", "field", "text"]


def fit_probabilities(features: dict) -> dict | None:
    """P(Good), P(Okay), P(Poor) for a resume–job pair from the logistic regression."""
    model = _load("fit_scorer.joblib")
    if model is None:
        return None
    x = np.array([[features.get(f) if features.get(f) is not None else 0.5 for f in FIT_FEATURES]])
    return {c: round(float(p), 3) for c, p in zip(model.classes_, model.predict_proba(x)[0])}


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()
