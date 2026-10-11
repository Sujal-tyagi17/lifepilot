"""Train and evaluate every model; write the models and metrics.json.

    python -m app.ml.train

Each model uses a stratified 80/20 train/test split (random_state=42). The
test set is never used for tuning. Numbers written to metrics.json are the
ones the ML Lab page shows.
"""
from __future__ import annotations

import csv
import json
import platform
import time
from collections import Counter
from pathlib import Path

import warnings

import joblib
import numpy as np
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
MODELS = HERE / "models"
SEED = 42
FIT_FEATURES = ["must", "nice", "role", "experience", "education", "field", "text"]
FIT_LABELS = ["Good", "Okay", "Poor"]


def _csv(name: str) -> list[dict]:
    path = DATA / name
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _report(y_true, y_pred, labels) -> dict:
    rep = classification_report(y_true, y_pred, labels=labels, output_dict=True, zero_division=0)
    return {
        "accuracy": round(accuracy_score(y_true, y_pred), 3),
        "macro_f1": round(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0), 3),
        "per_class": {k: {"precision": round(v["precision"], 3), "recall": round(v["recall"], 3),
                          "f1": round(v["f1-score"], 3), "support": int(v["support"])}
                      for k, v in rep.items() if k in labels},
        "labels": labels,
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
    }


def _split(X, y):
    return train_test_split(X, y, test_size=0.2, random_state=SEED, stratify=y)


# ── Role-family classifier ───────────────────────────────────────────

def train_role() -> dict:
    from app.jobs.catalog import classify_role_rules
    rows = _csv("role_jobs.csv")
    X = [r["text"] for r in rows]
    y = [r["family"] for r in rows]
    Xtr, Xte, ytr, yte = _split(X, y)
    model = Pipeline([
        # English stop words out, so "an" or "for" can never decide a role
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1, lowercase=True, stop_words="english")),
        ("svm", LinearSVC(C=1.0, random_state=SEED)),
    ])
    model.fit(Xtr, ytr)
    labels = sorted(set(y))
    ml = _report(yte, model.predict(Xte), labels)
    # Rules: the keyword classifier the app used before
    rules_pred = [classify_role_rules(t.split(".")[0], t)[0] or "none" for t in Xte]
    rules = {"accuracy": round(accuracy_score(yte, rules_pred), 3),
             "macro_f1": round(f1_score(yte, rules_pred, labels=labels, average="macro", zero_division=0), 3)}
    # A harder check: train only on template-made descriptions, test on the 51
    # hand-written sample roles the templates never saw
    tmpl = [(r["text"], r["family"]) for r in rows if r["source"] == "template"]
    real = [(r["text"], r["family"]) for r in rows if r["source"] != "template"]
    holdout = None
    if tmpl and real:
        m2 = Pipeline(model.steps).fit([t for t, _ in tmpl], [f for _, f in tmpl])
        holdout = {"rows": len(real), **{k: v for k, v in _report([f for _, f in real], m2.predict([t for t, _ in real]),
                                                                   labels).items() if k in ("accuracy", "macro_f1")}}
    model.fit(X, y)  # final model on all data
    joblib.dump(model, MODELS / "role_family.joblib")
    return {
        "name": "Job role-family classifier", "type": "TF-IDF (words and word pairs) + linear SVM",
        "used_for": "Role tag on every job; picks the roadmap template and the skills a short post usually asks for",
        "dataset": {"file": "role_jobs.csv", "rows": len(rows), "classes": len(labels),
                    "sources": dict(Counter(r["source"] for r in rows)), "train": len(Xtr), "test": len(Xte)},
        "test": ml, "rules_baseline": rules, "unseen_real_roles": holdout,
        "note": "Template-made descriptions are easier than real posts; the unseen real roles score is the fairer number.",
    }


# ── Job fit scorer ───────────────────────────────────────────────────

def _fit_rows() -> list[dict]:
    seed = _csv("fit_pairs.csv")
    team = _csv("fit_pairs_team.csv")
    if team:
        keys = {(r["job_text"], r["resume_text"]) for r in team}
        seed = [r for r in seed if (r["job_text"], r["resume_text"]) not in keys]
    return seed + team


def _fit_matrix(rows):
    return np.array([[float(r[f]) if r.get(f) not in (None, "") else 0.5 for f in FIT_FEATURES] for r in rows])


def _three_way(score: float, good: float, okay: float) -> str:
    return "Good" if score >= good else "Okay" if score >= okay else "Poor"


def train_fit() -> dict:
    rows = _fit_rows()
    X = _fit_matrix(rows)
    y = np.array([r["label"] for r in rows])
    rules_fit = np.array([float(r["rules_fit"]) for r in rows])
    idx = np.arange(len(rows))
    itr, ite = train_test_split(idx, test_size=0.2, random_state=SEED, stratify=y)
    model = LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced")
    model.fit(X[itr], y[itr])
    ml = _report(y[ite], model.predict(X[ite]), FIT_LABELS)

    # Rules baseline: the hand-set weights' fit score, cut at 70% / 45%
    rules = _report(y[ite], [_three_way(s, 0.7, 0.45) for s in rules_fit[ite]], FIT_LABELS)

    # Learned weights for the app's weighted fit score: how much each feature
    # pushes a pair from Poor towards Good (coefficients of Good minus Poor).
    classes = list(model.classes_)
    push = model.coef_[classes.index("Good")] - model.coef_[classes.index("Poor")]
    w = np.clip(push, 0, None)
    w = w / w.sum()
    w = np.maximum(w, 0.02)          # every signal keeps a small say (2%)
    w = w / w.sum()
    weights = {f: round(float(v), 3) for f, v in zip(FIT_FEATURES, w)}

    # Cut-offs for the weighted score, chosen on the training part only
    wscore = X @ np.array([weights[f] for f in FIT_FEATURES])
    best = (0, 0.7, 0.45)
    for good in np.arange(0.5, 0.95, 0.01):
        for okay in np.arange(0.2, good, 0.01):
            acc = accuracy_score(y[itr], [_three_way(s, good, okay) for s in wscore[itr]])
            if acc > best[0]:
                best = (acc, round(float(good), 2), round(float(okay), 2))
    learned = _report(y[ite], [_three_way(s, best[1], best[2]) for s in wscore[ite]], FIT_LABELS)

    model.fit(X, y)
    joblib.dump(model, MODELS / "fit_scorer.joblib")
    (MODELS / "fit_weights.json").write_text(json.dumps({"weights": weights, "cutoffs": {"good": best[1], "okay": best[2]},
                                                          "features": FIT_FEATURES}, indent=1))
    return {
        "name": "Job fit scorer", "type": "Logistic regression on 7 features (multinomial, balanced classes)",
        "used_for": "Fit score and its breakdown on every job card; the learned weights replace the hand-set ones",
        "dataset": {"file": "fit_pairs.csv" + (" + fit_pairs_team.csv" if _csv("fit_pairs_team.csv") else ""),
                    "rows": len(rows), "team_labels": len(_csv("fit_pairs_team.csv")),
                    "classes": dict(Counter(y.tolist())), "train": len(itr), "test": len(ite)},
        "features": FIT_FEATURES,
        "weights": {"hand_set": {"must": 0.40, "nice": 0.10, "role": 0.20, "experience": 0.10, "education": 0.10,
                                 "field": 0.05, "text": 0.05}, "learned": weights},
        "cutoffs": {"good": best[1], "okay": best[2]},
        "test": ml, "rules_baseline": {"accuracy": rules["accuracy"], "macro_f1": rules["macro_f1"],
                                       "confusion_matrix": rules["confusion_matrix"]},
        "learned_weights_test": {"accuracy": learned["accuracy"], "macro_f1": learned["macro_f1"]},
    }


# ── Text classifiers: intents and document types ─────────────────────

def _text_classifier(rows, text_key, label_key, ngram, file_name, cv=False):
    X = [r[text_key] for r in rows]
    y = [r[label_key] for r in rows]
    make = lambda: Pipeline([  # noqa: E731
        ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=ngram, sublinear_tf=True, lowercase=True)),
        ("lr", LogisticRegression(max_iter=3000, C=10.0)),
    ])
    Xtr, Xte, ytr, yte = _split(X, y)
    model = make().fit(Xtr, ytr)
    labels = sorted(set(y))
    out = {"test": _report(yte, model.predict(Xte), labels), "train": len(Xtr), "test_rows": len(Xte)}
    if cv:
        scores = cross_val_score(make(), X, y, cv=StratifiedKFold(5, shuffle=True, random_state=SEED), scoring="accuracy")
        out["cv5"] = {"mean": round(float(scores.mean()), 3), "std": round(float(scores.std()), 3),
                      "folds": [round(float(s), 3) for s in scores]}
    final = make().fit(X, y)
    joblib.dump(final, MODELS / file_name)
    return out, labels


def train_intent() -> dict:
    rows = _csv("intents.csv")
    out, labels = _text_classifier(rows, "text", "intent", (2, 5), "intent.joblib", cv=True)
    return {
        "name": "Assistant intent classifier", "type": "TF-IDF (character 2–5-grams, works for Hindi and Hinglish) + logistic regression",
        "used_for": "Routes each chat question to the right answer; intent badge in the chat",
        "dataset": {"file": "intents.csv", "rows": len(rows), "classes": len(labels),
                    "languages": dict(Counter(r["lang"] for r in rows)), "train": out["train"], "test": out["test_rows"]},
        "test": out["test"], "cv5": out["cv5"],
    }


def train_document() -> dict:
    rows = _csv("documents.csv")
    out, labels = _text_classifier(rows, "text", "type", (3, 5), "document_type.joblib")
    return {
        "name": "Document type classifier", "type": "TF-IDF (character 3–5-grams, robust to OCR mistakes) + logistic regression",
        "used_for": "Labels a scanned certificate (document scanner, Phase 4)",
        "dataset": {"file": "documents.csv", "rows": len(rows), "classes": len(labels),
                    "train": out["train"], "test": out["test_rows"]},
        "test": out["test"],
    }


# ── Skill extractor and semantic search (evaluated, not trained) ─────

def eval_skills() -> dict:
    from app.jobs.skills import SKILLS, extract_skills, extract_skills_fuzzy
    data = json.loads((DATA / "skill_eval.json").read_text(encoding="utf-8"))

    def score(fn):
        tp = fp = fn_ = 0
        for r in data:
            p, g = set(fn(r["text"])), set(r["skills"])
            tp, fp, fn_ = tp + len(p & g), fp + len(p - g), fn_ + len(g - p)
        prec, rec = tp / max(1, tp + fp), tp / max(1, tp + fn_)
        return {"precision": round(prec, 3), "recall": round(rec, 3), "f1": round(2 * prec * rec / max(1e-9, prec + rec), 3)}

    return {
        "name": "Skill extractor", "type": "Dictionary with aliases + fuzzy matching for typos + section-aware strength",
        "used_for": "Skill chips, What we read from your resume, focus areas, roadmap",
        "dataset": {"file": "skill_eval.json", "rows": len(data), "dictionary_skills": len(SKILLS),
                    "aliases": sum(len(v) for v in SKILLS.values())},
        "test": score(extract_skills_fuzzy), "rules_baseline": score(extract_skills),
        "note": "Baseline is exact matching only; the model adds fuzzy matching for typos.",
    }


def eval_search() -> dict:
    data = json.loads((DATA / "search_eval.json").read_text(encoding="utf-8"))
    base = {"name": "Semantic scheme search", "type": "Sentence embeddings (ChromaDB's built-in all-MiniLM-L6-v2)",
            "used_for": "Scheme search and the assistant's scheme lookup",
            "dataset": {"file": "search_eval.json", "rows": len(data)}}
    try:
        from app.knowledge.vectorstore import search
        hits = 0
        for r in data:
            ids = [d.get("id") for d in search(r["query"], n_results=5)]
            hits += r["expect"] in ids
        if not hits and not search("scholarship", n_results=1):
            raise RuntimeError("the vector store is empty or unavailable")
        # Keyword baseline: share of query words found in the scheme text
        from app.knowledge.vectorstore import DATA_FILE
        schemes = json.loads(Path(DATA_FILE).read_text(encoding="utf-8"))
        kw_hits = 0
        for r in data:
            words = {w for w in r["query"].lower().split() if len(w) > 2}
            ranked = sorted(schemes, key=lambda s: -sum(w in json.dumps(s).lower() for w in words))
            kw_hits += r["expect"] in [s["id"] for s in ranked[:5]]
        return {**base, "test": {"recall_at_5": round(hits / len(data), 3)},
                "rules_baseline": {"recall_at_5": round(kw_hits / len(data), 3)}}
    except Exception as e:
        return {**base, "test": None, "skipped": f"Not evaluated on this machine: {e}"}


def main() -> None:
    warnings.filterwarnings("ignore", message="Unknown solver options")
    MODELS.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    metrics = {"trained_at": time.strftime("%Y-%m-%d %H:%M"), "sklearn": sklearn.__version__,
               "python": platform.python_version(), "split": "stratified 80/20, random_state=42", "models": {}}
    for key, fn in [("fit", train_fit), ("role", train_role), ("skills", eval_skills),
                    ("document", train_document), ("intent", train_intent), ("search", eval_search)]:
        print(f"• {key} …", end=" ", flush=True)
        m = fn()
        metrics["models"][key] = m
        t = m.get("test") or {}
        print({k: t[k] for k in ("accuracy", "macro_f1", "precision", "recall", "recall_at_5") if k in t} or m.get("skipped"))
    metrics["seconds"] = round(time.time() - t0, 1)
    (MODELS / "metrics.json").write_text(json.dumps(metrics, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Done in {metrics['seconds']}s → {MODELS}")


if __name__ == "__main__":
    main()
