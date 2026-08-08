from __future__ import annotations

import importlib
import sys

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def app_module(tmp_path, monkeypatch):
    monkeypatch.setenv("OMNI_DB_PATH", str(tmp_path / "test-omni.db"))
    monkeypatch.setenv("OMNI_DEMO_MODE", "1")
    monkeypatch.setenv("OMNI_AI_DEMO_MODE", "1")
    monkeypatch.setenv("OMNI_OFFLINE_MODE", "1")
    monkeypatch.setenv("OMNI_SESSION_SECRET", "test-session-secret-that-is-long-enough-1234567890")
    monkeypatch.setenv("OMNI_RELOAD", "0")
    monkeypatch.setenv("OMNI_INTELLIGENCE_CACHE_SECONDS", "300")

    for name in ("app", "omni_store", "omni_ai"):
        sys.modules.pop(name, None)
    module = importlib.import_module("app")
    monkeypatch.setattr(module.store, "LEGACY_VAULT_PATH", tmp_path / "signals_vault.json")

    async def fake_intelligence(*_args, **_kwargs):
        streams = [
            {
                "key": "macro", "label": "Macro", "status": "live", "completeness": 1,
                "source": "test", "as_of": "2026-07-13", "summary": "EUR/USD 1.10",
                "metrics": {"eur_usd_spot": 1.10, "eur_usd_30d_change_pct": 0.4},
            },
            {
                "key": "markets", "label": "Markets", "status": "live", "completeness": 1,
                "source": "test", "as_of": "2026-07-13", "summary": "Test market",
                "metrics": {
                    "btc": {"usd": 60000, "change_24h_pct": 1.0},
                    "eth": {"usd": 3000, "change_24h_pct": 0.5},
                    "gold_proxy_paxg": {"usd": 2400, "change_24h_pct": 0.1},
                },
            },
            {
                "key": "rates_risk", "label": "Rates", "status": "live", "completeness": 1,
                "source": "test", "as_of": "2026-07-13", "summary": "Rates test",
                "metrics": {
                    "^TNX": {"price": 4.2}, "^VIX": {"price": 16.0}, "DX-Y.NYB": {"price": 101.0}
                },
            },
            {
                "key": "supply_chain", "label": "Supply", "status": "live", "completeness": 1,
                "source": "test", "as_of": "2026-07-13", "summary": "Supply test",
                "metrics": {"BZ=F": {"price": 80}, "HG=F": {"price": 4.4}, "GC=F": {"price": 2400}},
            },
            {
                "key": "attention", "label": "Attention", "status": "live", "completeness": 1,
                "source": "test", "as_of": "2026-07-13", "summary": "Attention test",
                "metrics": {"front_page_count": 10, "top_headlines": [{"title": "Safe test", "points": 1}]},
            },
        ]
        return {
            "coverage_live": 5.0, "coverage_total": 5, "coverage_label": "5/5",
            "captured_at": "2026-07-13T00:00:00Z", "cache_status": "test", "streams": streams,
        }

    monkeypatch.setattr(module, "gather_market_intelligence", fake_intelligence)
    return module


@pytest.fixture()
def client(app_module):
    with TestClient(app_module.app) as test_client:
        yield test_client


def answer_questions(intake_data: dict) -> dict[str, str]:
    answers: dict[str, str] = {}
    for question in intake_data["questions"]:
        if question.get("options"):
            answers[question["id"]] = question["options"][0]["value"]
        else:
            answers[question["id"]] = "مهارت فروش، تحقیق بازار و زبان انگلیسی"
    return answers


@pytest.fixture()
def completed_analysis(client):
    query = "من ۵ هزار دلار سرمایه دارم و روزی ۲ ساعت برای ساخت درآمد پایدار وقت می‌گذارم"
    intake_response = client.post(
        "/api/intake", json={"query": query, "tier": "B2C", "horizon": "strategic"}
    )
    assert intake_response.status_code == 200
    intake = intake_response.json()["data"]
    response = client.post(
        "/api/analyze",
        json={"session_id": intake["session_id"], "answers": answer_questions(intake)},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]
