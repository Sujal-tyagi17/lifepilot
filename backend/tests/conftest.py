"""Shared test setup: isolated SQLite DB, mock LLM, no network.

Environment variables are set before the app is imported, because
app.config reads them at import time.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

_tmp = tempfile.mkdtemp(prefix="lifepilot-tests-")
os.environ.update({
    "DATABASE_URL": f"sqlite:///{_tmp}/test.db",
    "LLM_PROVIDER": "mock",
    "SCRAPING_ENABLED": "false",
    "CHROMA_PERSIST_DIR": f"{_tmp}/chroma",
    "KINDE_DOMAIN": "",
    "KINDE_CLIENT_ID": "",
    "SERPER_API_KEY": "",
    "ADZUNA_APP_ID": "",
    "ADZUNA_APP_KEY": "",
})
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.knowledge import vectorstore  # noqa: E402

# The real vector store downloads an embedding model; tests use the in-memory fallback.
vectorstore.get_vectorstore = lambda: vectorstore._FallbackCollection()
vectorstore.search = lambda *a, **k: []
import app.knowledge.rag as rag  # noqa: E402

rag.vector_search = lambda *a, **k: []

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

PROFILE = {
    "name": "Aisha Kumar", "age": 21, "gender": "Female", "state": "Karnataka",
    "category": "OBC", "education_level": "Undergraduate", "field_of_study": "Engineering",
    "annual_income": 300000, "goals": "Finish B.Tech and later start a company",
}


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def guest(client):
    """A fresh guest profile: (profile_id, headers carrying its key)."""
    r = client.post("/api/profiles", json=PROFILE)
    assert r.status_code == 201, r.text
    body = r.json()
    return body["id"], {"X-Profile-Key": body["guest_key"]}
