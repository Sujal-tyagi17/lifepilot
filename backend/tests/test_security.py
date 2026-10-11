"""Ownership and auth fixes (S1, S2, S4, S5, S6)."""
import jwt
import pytest
from fastapi import HTTPException

from app.auth import verify_kinde_token
from tests.conftest import PROFILE


def test_no_endpoint_lists_all_profiles(client, guest):
    # S1: GET /api/profiles used to return every user's profile
    assert client.get("/api/profiles").status_code == 405


def test_profile_routes_require_the_guest_key(client, guest):
    pid, headers = guest
    for method, url in [("get", f"/api/profiles/{pid}"), ("post", f"/api/agent/run/{pid}"),
                        ("get", f"/api/agent/runs/{pid}"), ("get", f"/api/agent/calendar/{pid}"),
                        ("delete", f"/api/profiles/{pid}")]:
        assert getattr(client, method)(url).status_code == 404, url
        assert getattr(client, method)(url, headers={"X-Profile-Key": "wrong"}).status_code == 404, url
    assert client.get(f"/api/profiles/{pid}", headers=headers).status_code == 200


def test_runs_and_assistant_are_protected(client, guest):
    pid, headers = guest
    run_id = client.post(f"/api/agent/run/{pid}", headers=headers).json()["id"]
    assert client.get(f"/api/agent/run/{run_id}").status_code == 404
    assert client.get(f"/api/agent/run/{run_id}", headers=headers).status_code == 200
    q = {"profile_id": pid, "question": "documents?"}
    assert client.post("/api/agent/assistant", json=q).status_code == 404
    assert client.post("/api/agent/assistant", json=q, headers=headers).status_code == 200


def test_user_id_in_body_is_ignored(client):
    # A guest must not be able to plant a profile into someone else's account
    body = client.post("/api/profiles", json={**PROFILE, "user_id": "victim-user"}).json()
    assert body["user_id"] is None


def test_guest_update_keeps_one_profile(client, guest):
    pid, headers = guest
    r = client.post("/api/profiles", json={**PROFILE, "annual_income": 200000}, headers=headers)
    assert r.json()["id"] == pid and r.json()["annual_income"] == 200000


def test_delete_with_key(client, guest):
    pid, headers = guest
    assert client.delete(f"/api/profiles/{pid}", headers=headers).status_code == 204
    assert client.get(f"/api/profiles/{pid}", headers=headers).status_code == 404


def test_forged_token_is_rejected(client):
    # S5: tokens that failed signature checks used to be decoded without verification
    forged = jwt.encode({"sub": "victim"}, "not-the-real-key-but-long-enough-for-hs256", algorithm="HS256")
    with pytest.raises(HTTPException):
        verify_kinde_token(forged)
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"}).json()["authenticated"] is False


def test_mock_guest_token_only_when_auth_not_configured(monkeypatch):
    from app import auth

    assert verify_kinde_token("guest_mock_access_token")["sub"] == "guest_citizen"
    monkeypatch.setattr(auth.settings, "kinde_domain", "https://example.kinde.com")
    monkeypatch.setattr(auth.settings, "kinde_client_id", "abc")
    monkeypatch.setattr(auth, "get_jwks_client", lambda: None)
    with pytest.raises(HTTPException):
        verify_kinde_token("guest_mock_access_token")


@pytest.mark.parametrize("url", [
    "http://169.254.169.254/latest/meta-data",
    "https://localhost/admin",
    "https://evil.com/?x=.gov.in",
    "https://scholarships.gov.in.evil.com/",
])
def test_scrape_only_allows_government_portals(client, url):
    # S6: the scrape endpoint used to fetch any URL (server-side request forgery)
    assert client.post("/api/opportunities/scrape", json={"urls": [url]}).status_code == 400


def test_csp_allows_no_external_scripts(client):
    csp = client.get("/api/health").headers["content-security-policy"]
    assert "script-src 'self'" in csp
    assert "unsafe-eval" not in csp and "cdn." not in csp and "unpkg" not in csp


def test_ui_files_are_always_revalidated(client):
    # Stale cached modules after an update used to leave a blank page
    for path in ["/", "/static/js/main.js", "/static/css/app.css"]:
        r = client.get(path)
        assert r.status_code == 200, path
        assert r.headers["cache-control"] == "no-cache", path
    assert "no-cache" not in client.get("/api/health").headers.get("cache-control", "")
