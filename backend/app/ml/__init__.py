"""Machine learning in LifePilot (Phase 3).

Six models, each with its own dataset, metric and place in the app:

    model                    type                              used by
    job fit scorer           logistic regression, 7 features   fit score on every job card
    role-family classifier   TF-IDF + linear SVM               role tag on jobs; picks the roadmap
    skill extractor          dictionary + fuzzy + sections     skill chips, focus areas, roadmap
    document type            TF-IDF + logistic regression      document scanner (Phase 4)
    assistant intent         TF-IDF + logistic regression      routes chat questions; intent badge
    semantic search          sentence embeddings (ChromaDB)    scheme search

Eligibility for schemes stays rule-based: the law is a rule. ML is used for
reading, matching and ranking.

    python -m app.ml.make_data   # rebuild the seed datasets in app/ml/data/
    python -m app.ml.train       # train, evaluate, write app/ml/models/ and metrics.json
"""
