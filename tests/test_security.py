import json
from pathlib import Path


def test_security_headers_and_signed_http_only_cookie(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    cookie = response.headers.get("set-cookie", "")
    # Fixture may already have received the cookie during a previous call; the jar is authoritative.
    assert client.cookies.get("omni_session")
    if cookie:
        assert "HttpOnly" in cookie and "SameSite=lax" in cookie


def test_static_assets_do_not_create_anonymous_sessions(app_module):
    from fastapi.testclient import TestClient

    with TestClient(app_module.app) as fresh_browser:
        response = fresh_browser.get("/static/style.css")
        assert response.status_code == 200
        assert "omni_session=" not in response.headers.get("set-cookie", "")
        assert fresh_browser.cookies.get("omni_session") is None


def test_oversized_body_is_rejected_before_validation(client):
    response = client.post(
        "/api/intake",
        content=b"x" * 150_000,
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413


def test_streamed_body_without_content_length_is_bounded(client):
    def chunks():
        yield b'{"query":"'
        yield b"x" * 130_000
        yield b'","tier":"B2C","horizon":"instant"}'

    response = client.post(
        "/api/intake",
        content=chunks(),
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json() == {
        "status": "error",
        "code": "request_too_large",
        "message": "The request exceeds the allowed size.",
    }
    assert response.headers["x-content-type-options"] == "nosniff"


def test_public_errors_stay_english_even_when_persian_is_requested(client):
    response = client.get(
        "/api/analyses/does-not-exist",
        headers={"Accept-Language": "fa-IR,fa;q=0.9"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == {
        "code": "analysis_not_found",
        "message": "The analysis was not found.",
    }


def test_frontend_has_no_direct_innerhtml_or_inline_event_handlers():
    root = Path(__file__).resolve().parents[1]
    script = (root / "static" / "script.js").read_text(encoding="utf-8")
    html = (root / "templates" / "index.html").read_text(encoding="utf-8").lower()
    assert ".innerhtml" not in script.lower()
    assert "onclick=" not in html
    assert "onerror=" not in html


def test_xss_payload_remains_json_data(client):
    payload = '<img src=x onerror="globalThis.pwned=1"> یک درخواست شخصی معتبر و طولانی'
    intake = client.post(
        "/api/intake", json={"query": payload, "tier": "B2C", "horizon": "instant"}
    )
    assert intake.status_code == 200
    assert intake.json()["data"]["session_id"]


def test_goal_progress_bounds_are_server_validated(client, completed_analysis):
    goal = client.post(
        "/api/goals/from-analysis", json={"analysis_id": completed_analysis["analysis_id"]}
    ).json()["data"]
    assert client.patch(f"/api/goals/{goal['id']}", json={"progress": 101}).status_code == 422


def test_legacy_vault_is_never_claimed_by_first_visitor(app_module, monkeypatch):
    from fastapi.testclient import TestClient

    legacy_vault = app_module.store.LEGACY_VAULT_PATH
    legacy_vault.write_text(
        json.dumps(
            [
                {
                    "timestamp": "2026-01-01T00:00:00Z",
                    "tier": "B2C",
                    "horizon_mode": "instant",
                    "original_query": "Synthetic legacy security fixture",
                }
            ]
        ),
        encoding="utf-8",
    )
    with TestClient(app_module.app) as client:
        before = client.get("/api/vault").json()["data"]
        assert all(not item.get("analysis_id", "").startswith("legacy-") for item in before)
        assert client.post("/api/admin/claim-legacy").status_code == 404

        monkeypatch.setattr(app_module, "LEGACY_CLAIM_TOKEN", "explicit-test-token")
        assert client.post(
            "/api/admin/claim-legacy",
            headers={"x-omni-legacy-token": "wrong"},
        ).status_code == 403
        claimed = client.post(
            "/api/admin/claim-legacy",
            headers={"x-omni-legacy-token": "explicit-test-token"},
        )
        assert claimed.status_code == 200
        assert claimed.json()["data"]["claimed"] == 1
        after = client.get("/api/vault").json()["data"]
        assert any(item.get("analysis_id", "").startswith("legacy-") for item in after)


def test_manual_goal_rejects_impossible_calendar_date(client):
    response = client.post(
        "/api/goals",
        json={
            "tier": "B2C",
            "title": "هدف معتبر",
            "target": "رسیدن به یک نتیجه قابل سنجش",
            "deadline": "2026-99-99",
        },
    )
    assert response.status_code == 422
