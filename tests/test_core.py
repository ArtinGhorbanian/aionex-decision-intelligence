import pytest

from omni_intake import extract_facts_from_query


def test_persian_digit_fact_extraction():
    query = "من ۵ هزار دلار سرمایه و روزی ۲ ساعت زمان دارم"
    facts = extract_facts_from_query(query, "B2C")
    assert facts["capital"] == "5 هزار دلار"
    assert facts["available_time"] == "2 ساعت"


def test_confidence_integrity_uses_independent_usable_source_ratio(app_module):
    capped = app_module.enforce_confidence_integrity("High", 2, 5)
    assert capped["confidence"] == "Low"
    assert capped["capped"] is True
    allowed = app_module.enforce_confidence_integrity("High", 4, 5)
    assert allowed["confidence"] == "High"


def test_prediction_builder_deduplicates_metrics(app_module):
    intel = {
        "streams": [{
            "key": "macro", "status": "live", "metrics": {"eur_usd_spot": 1.1}
        }]
    }
    data = {
        "confidence": "Moderate", "signal_name": "test", "horizon_mode": "instant",
        "predictions": [
            {
                "metric": "eur_usd", "direction": "up", "horizon_days": 7,
                "rationale": "a", "invalidation_condition": "EUR/USD closes below 1.05",
            },
            {"metric": "eur_usd", "direction": "down", "horizon_days": 9, "rationale": "b"},
        ],
    }
    records = app_module.build_predictions_from_ai(data, intel, "query", "B2C")
    assert len(records) == 1
    assert records[0]["invalidation_condition"] == "EUR/USD closes below 1.05"


@pytest.mark.asyncio
async def test_prediction_resolution_is_offline_and_never_calls_yahoo_by_default(
    client, app_module, monkeypatch
):
    assert app_module.OFFLINE_MODE is True
    assert app_module.PREDICTION_NETWORK_ENABLED is False
    assert app_module.PREDICTION_SWEEPER_ENABLED is False
    assert not hasattr(app_module, "_yahoo_quote")
    assert "query1.finance.yahoo.com" not in app_module.Path(
        app_module.__file__
    ).read_text(encoding="utf-8")

    class UnexpectedNetworkClient:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("offline prediction resolution must not open a client")

    monkeypatch.setattr(app_module.httpx, "AsyncClient", UnexpectedNetworkClient)
    values = await app_module.fetch_current_metric_values({"eur_usd", "btc", "us10y"})
    assert values == {"eur_usd": None, "btc": None, "us10y": None}


def test_health_reports_demo_storage_and_prediction_readiness_truthfully(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["service"] == "aionex"
    assert data["operational_status"] == "ready"
    assert data["ready"] is True
    assert data["storage_ready"] is True
    assert data["ai_ready"] is True
    assert data["ai_provider_configured"] is False
    assert data["generation_mode"] == "demo"
    assert data["offline_mode"] is True
    assert data["prediction_resolution"] == {
        "network_enabled": False,
        "sweeper_enabled": False,
    }
