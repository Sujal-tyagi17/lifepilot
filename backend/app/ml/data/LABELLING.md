# Datasets and labelling rules

All files here are plain CSV or JSON. `python -m app.ml.make_data` rebuilds the
seed files; `python -m app.ml.train` trains every model from them.

**Honesty note.** The seed data is generated from written templates and the
rules below. It is a starting point so the models can be trained and
evaluated end to end. The team should review and relabel examples (the ML Lab
has a Label tab for job-fit pairs; its labels go to `fit_pairs_team.csv` and
override the seed labels when you retrain). Report the dataset sources and
sizes from the ML Lab, which reads `app/ml/models/metrics.json`.

| File | Rows | What it is |
|---|---|---|
| `role_jobs.csv` | ~555 | Job descriptions with their role family. 51 are the curated sample roles; the rest are built from per-family templates (titles, duties, required and good-to-have skills, experience, boilerplate). |
| `fit_pairs.csv` | 260 | A synthetic resume and a job, the seven fit features the matcher computes for them, the old rule-based fit score, and a Good / Okay / Poor label from the rubric below. Balanced, about a third each. |
| `fit_pairs_team.csv` | grows | Labels added by the team in the ML Lab. Same columns; these win over the seed labels. |
| `intents.csv` | ~220 | Questions people ask the assistant, in English, Hindi and Hinglish, with one of 6 intents. |
| `documents.csv` | 240 | Text as OCR reads it from 8 types of certificate (30 each), with OCR-style mistakes. All names are made up; ID numbers are masked (XXXX). |
| `skill_eval.json` | 20 | Short resume snippets, some with typos, and the skills a person would list for them. Used only to test the skill extractor. |
| `search_eval.json` | 30 | Search queries and the scheme that must appear in the top 5. Used only to test semantic search. |

## Job-fit rubric (Good / Okay / Poor)

Facts used: the job's must-have skills, which of them the person has and
whether the resume proves them (used at work or in a project), whether the job
is the kind of role they want, the years asked for, and the education asked for.

1. **Poor** if any of these is true:
   - their education is below what the job asks for;
   - the job asks for 3 or more years more experience than they have;
   - it is not the kind of role they want **and** they have under 40% of the must-have skills.
2. **Good** if all of these are true:
   - it is the kind of role they want;
   - they have at least 75% of the must-have skills;
   - at least half of those are proved in a job or project, not just listed;
   - the job asks for at most 1 year more experience than they have.
3. Otherwise **Okay**.

When two people disagree on a label, a third person decides. Write down any
change to these rules in the project report.

## Intents

`eligibility` (which schemes can I get), `documents` (papers needed),
`deadlines` (last dates), `benefits` (amounts), `how_to_apply` (process,
links), `jobs` (jobs, skills, careers).

## Document types

`aadhaar`, `income`, `caste`, `domicile`, `disability`, `marksheet`,
`bank_passbook`, `fee_receipt`.
