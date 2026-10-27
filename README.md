# LifePilot

**Scholarships, government schemes and jobs, checked against your profile.**
Available in English, हिन्दी, বাংলা, मराठी, తెలుగు and தமிழ்.

You tell LifePilot about yourself once: your studies, family income, category and state, and a resume if you have one. It then tells you:

- which schemes you qualify for, and why;
- which documents to get, and in what order;
- which jobs fit you, and a week-by-week plan to get ready for them.

Eligibility is decided by each scheme's published rules, never by an AI guess. Machine learning is used for reading resumes and certificates, matching jobs and understanding questions.

> First time? **[SETUP.md](SETUP.md)** covers installation, running and how the team works with Git.

## Run it

```powershell
cd backend
.\run.ps1
```

Open **http://localhost:8000**. The first run installs everything; later runs start in seconds. macOS and Linux: see [SETUP.md](SETUP.md#3-run-it).

It works with no account and no API key. Optional keys in `backend/.env`:

| Key | Adds |
|---|---|
| `GROQ_API_KEY` | Assistant answers written by an LLM |
| `SERPER_API_KEY` or `SERPAPI_KEY` | Live job openings (LinkedIn, Naukri, Indeed, company sites) |
| `ADZUNA_APP_ID` + `ADZUNA_APP_KEY`, `JOOBLE_API_KEY` | More job sources |

## Features

| Area | What you get |
|---|---|
| **Schemes** | A verdict with reasons for every scheme; a **What if** simulator; **What would change it?** (the smallest honest change that unlocks more schemes); a **Scheme map** of schemes, documents and rules |
| **Documents** | One checklist for all your schemes; a **scanner** that reads a certificate in your browser and checks it against your profile; files never leave your device |
| **Planning** | A **weekly plan** fitted to your hours (0/1 knapsack, earliest deadline first); deadlines to your calendar; a printable action plan |
| **Jobs** | Resume reading with proof-weighted skills; live openings, your state first; an ML **fit score** with its breakdown; the best next skill; a roadmap for each job |
| **Assistant** | Answers about your own results, by text or **voice**. Hindi and English answers work even without an LLM key; with an LLM key it can also reply in the other interface languages |
| **ML Lab** | Six trained models with real test accuracy and a box to try each one (`#/ml-lab`) |

### The models

| Model | Method |
|---|---|
| Job fit scorer | Logistic regression on 7 job–resume features |
| Role classifier | TF-IDF + linear SVM, 21 job families |
| Question intent | Character n-grams + logistic regression, 7 intents |
| Document type | Logistic regression on certificate text |
| Skill matcher | Fuzzy matching against a skill dictionary |
| Profile parser | "Describe yourself in one line" fills the form |

## How it is built

- **Backend:** Python, FastAPI, SQLAlchemy, SQLite (PostgreSQL via `DATABASE_URL`), scikit-learn.
- **Frontend:** plain JavaScript modules and CSS. No framework, no build step.
- **In the browser:** Tesseract.js (OCR) and Cytoscape.js (graph), served from `frontend/vendor/`.

```
backend/app/
  agents/      scheme-checking pipeline
  services/    eligibility, counterfactuals, planner, graph, document check
  jobs/        resume reading, job sources, fit scoring, roadmaps
  ml/          datasets, training, prediction
  knowledge/   assistant
  routers/     API endpoints
frontend/
  js/          one module per page; js/lang/ holds the translations
  css/ fonts/ vendor/
```

API docs: **http://localhost:8000/docs**

## Privacy

- Documents and scan images stay in your browser. Only the text read from a scan is sent to be checked, and it is not stored.
- Guest profiles are tied to a key in your browser; nobody else can read them.
- Every script, font and icon is served by the app itself.
- Voice input uses the browser's speech service (Chrome and Edge send the audio to Google or Microsoft).

LifePilot is not a government website. Always confirm details on the official portal before you apply.

## Tests

```powershell
cd backend
.venv\Scripts\python -m pytest -q
```

## Credits

[Anek](https://github.com/EkType/Anek) fonts (OFL) · [Lucide](https://lucide.dev) icons (ISC) · [Tesseract.js](https://github.com/naptha/tesseract.js) (Apache 2.0) · [Cytoscape.js](https://js.cytoscape.org) (MIT). Licence texts are in `frontend/fonts/` and `frontend/vendor/`.
