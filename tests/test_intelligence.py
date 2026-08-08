from __future__ import annotations

import inspect
import json
import re
from datetime import datetime, timezone

import httpx
import omni_intelligence as intelligence
import pytest


CORE_SOURCE_KEYS = {
    "ecb_fx",
}


def _serialized_size(value: object) -> int:
    return len(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    )


def test_source_registry_is_unique_keyless_and_declared_free():
    specs = intelligence.SOURCE_SPECS
    assert len(specs) >= 15
    assert len({spec.key for spec in specs}) == len(specs)
    assert len({spec.layer for spec in specs}) >= 10

    for spec in specs:
        assert spec.key
        assert spec.label
        assert spec.source
        assert spec.source_url.startswith("https://")
        assert callable(spec.fetcher)
        assert spec.ttl_seconds > 0
        assert spec.stale_seconds >= spec.ttl_seconds
        assert spec.authority in {"official", "public", "community"}

    catalog = intelligence.assemble_intelligence([], []).get("source_catalog")
    assert catalog and len(catalog) == len(specs)
    assert all(item["api_cost_usd"] == 0 for item in catalog)
    assert all(item["requires_api_key"] is False for item in catalog)


def test_no_active_source_or_module_endpoint_uses_yahoo_hosts():
    for spec in intelligence.SOURCE_SPECS:
        attribution = f"{spec.provider} {spec.source_url}".casefold()
        assert "yahoo" not in attribution
    module_source = inspect.getsource(intelligence).casefold()
    assert "finance.yahoo.com" not in module_source
    assert "query1.finance" not in module_source


def test_production_module_has_no_mojibake_or_persian_routing_literals():
    module_source = inspect.getsource(intelligence)

    assert re.search(r"[\u00c2\u00c3\u00e2\u00d8\u00d9\ufffd]", module_source) is None
    assert re.search(r"[\u0600-\u06ff]", module_source) is None


def test_source_selection_is_relevant_bounded_and_keeps_core_context():
    b2c, b2c_tags = intelligence.select_source_specs(
        "I want a software freelancing path based on in-demand skills",
        "B2C",
        "instant",
    )
    b2b, b2b_tags = intelligence.select_source_specs(
        "Our United States supplier operation needs regulatory compliance planning",
        "B2B",
        "strategic",
    )

    for selected in (b2c, b2b):
        keys = [spec.key for spec in selected]
        assert CORE_SOURCE_KEYS.issubset(keys)
        assert len(keys) == len(set(keys))
        assert len(keys) <= intelligence.MAX_SELECTED_SOURCES

    assert {"b2c", "skills", "technology"}.issubset(b2c_tags)
    assert {"b2b", "geography_us", "regulation", "strategic"}.issubset(
        b2b_tags
    )
    assert "stackoverflow_skills" in {spec.key for spec in b2c}
    assert "regulations" in {spec.key for spec in b2b}
    assert {spec.key for spec in b2c} != {spec.key for spec in b2b}


@pytest.mark.parametrize(
    "query",
    [
        "I run retail email campaigns for local shops",
        "Help improve our retail and email conversion rate",
    ],
)
def test_ai_token_boundary_does_not_misroute_retail_or_email(query):
    selected, tags = intelligence.select_source_specs(query, "B2C")
    keys = {spec.key for spec in selected}

    assert "technology" not in tags
    assert "attention" not in keys
    assert "github_demand" not in keys
    assert "stackoverflow_skills" not in keys


def test_manageable_business_risk_does_not_activate_natural_hazards():
    selected, tags = intelligence.select_source_specs(
        "I need a manageable low-risk side income plan", "B2C"
    )
    keys = {spec.key for spec in selected}

    assert "risk" in tags
    assert not keys & {
        "earthquakes",
        "natural_events",
        "us_weather_alerts",
        "space_weather",
    }


def test_generic_b2b_has_only_the_official_baseline_not_random_branches():
    selected, tags = intelligence.select_source_specs(
        "Help us grow our consulting business", "B2B"
    )
    keys = {spec.key for spec in selected}

    assert tags == ["b2b", "core"]
    assert keys == CORE_SOURCE_KEYS
    assert not keys & {"eu_tenders", "food_safety", "natural_events"}


def test_explicit_eu_cyber_tender_routes_both_precise_official_branches():
    selected, tags = intelligence.select_source_specs(
        "Find European Union cybersecurity tender opportunities", "B2B"
    )
    keys = {spec.key for spec in selected}

    assert {"cyber", "procurement", "geography_eu"}.issubset(tags)
    assert {"cyber_risk", "eu_tenders"}.issubset(keys)
    assert "food_safety" not in keys
    assert not keys & {"earthquakes", "natural_events", "us_weather_alerts"}


def test_geography_gates_california_weather_and_eu_procurement():
    california, _ = intelligence.select_source_specs(
        "California weather alerts for warehouse continuity", "B2B"
    )
    berlin, _ = intelligence.select_source_specs(
        "Berlin weather alerts for warehouse continuity", "B2B"
    )
    us_bid, _ = intelligence.select_source_specs(
        "United States government tender bid", "B2B"
    )
    eu_bid, _ = intelligence.select_source_specs(
        "European Union government tender bid", "B2B"
    )
    us_food, _ = intelligence.select_source_specs(
        "US food safety recall compliance", "B2B"
    )
    generic_food, _ = intelligence.select_source_specs(
        "Improve my restaurant menu", "B2B"
    )

    assert "us_weather_alerts" in {spec.key for spec in california}
    assert "us_weather_alerts" not in {spec.key for spec in berlin}
    assert "eu_tenders" not in {spec.key for spec in us_bid}
    assert "eu_tenders" in {spec.key for spec in eu_bid}
    assert "food_safety" in {spec.key for spec in us_food}
    assert "food_safety" not in {spec.key for spec in generic_food}


def test_local_routing_context_can_activate_a_branch_without_leaving_raw_text():
    selected, tags = intelligence.select_source_specs(
        "Help me plan this service",
        "B2C",
        routing_context="I know Python software development and want freelance work",
    )

    assert {"technology", "skills"}.issubset(tags)
    assert "stackoverflow_skills" in {spec.key for spec in selected}


def test_compact_ai_evidence_has_an_absolute_4000_character_ceiling():
    streams = [
        {
            "key": spec.key,
            "layer": spec.layer,
            "status": "live",
            "as_of": "2026-07-13T00:00:00Z",
            "summary": f"{spec.label}: " + ("observation " * 2_000),
            "source": spec.source + (" source" * 500),
            "authority": spec.authority,
            "limitation": spec.limitation + (" limitation" * 500),
            "metrics": {"raw_payload_must_not_be_forwarded": "x" * 20_000},
        }
        for spec in intelligence.SOURCE_SPECS
    ]
    raw = {
        "captured_at": "2026-07-13T00:00:00Z",
        "coverage_label": f"{len(streams)}/{len(streams)}",
        "routing_tags": ["technology", "supply", "regulation"],
        "streams": streams,
    }

    packet = intelligence.compact_intelligence_for_ai(raw, max_chars=100_000)
    assert _serialized_size(packet) <= 4_000
    assert packet["cost"] == {
        "external_api_cost_usd": 0,
        "additional_model_calls": 0,
    }
    assert packet["omitted_selected_sources"] > 0
    assert all("metrics" not in item for item in packet["evidence"])
    assert all(len(item["observation"]) <= 360 for item in packet["evidence"])


def test_one_source_failure_is_isolated_and_preserves_free_metadata():
    good_spec, failed_spec = intelligence.SOURCE_SPECS[:2]
    good = {
        "key": good_spec.key,
        "label": good_spec.label,
        "layer": good_spec.layer,
        "source": good_spec.source,
        "source_url": good_spec.source_url,
        "authority": good_spec.authority,
        "api_cost_usd": 0,
        "requires_api_key": False,
        "limitation": good_spec.limitation,
        "as_of": "2026-07-13",
        "metrics": {"signal": 1.0},
        "summary": "A healthy deterministic fixture.",
    }

    result = intelligence.assemble_intelligence(
        [good, RuntimeError("source unavailable")],
        [good_spec, failed_spec],
        ["core"],
    )

    assert result["coverage_total"] == 2
    assert result["coverage_live"] == round(
        result["streams"][0]["quality"]["weighted"], 2
    )
    assert 0 < result["coverage_live"] < 1
    assert result["all_external_apis_free"] is True
    assert result["external_api_cost_usd"] == 0
    assert result["streams"][0]["status"] == "live"
    degraded = result["streams"][1]
    assert degraded["status"] == "degraded"
    assert degraded["error"] == "RuntimeError"
    assert degraded["api_cost_usd"] == 0
    assert degraded["requires_api_key"] is False
    for stream in result["streams"]:
        spec = intelligence.SOURCE_BY_KEY[stream["key"]]
        assert stream["provider"] == spec.provider
        assert stream["source_url"] == spec.source_url
        assert "as_of" in stream
        assert stream["cache"]["status"] == stream["cache_status"]
        assert stream["freshness"]["score"] == stream["quality"]["freshness"]


def test_evidence_is_sorted_usable_official_first_and_drops_degraded_from_ai():
    official = intelligence.SOURCE_BY_KEY["ecb_fx"]
    public = intelligence.SOURCE_BY_KEY["attention"]
    failed = intelligence.SOURCE_BY_KEY["cyber_risk"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def fixture(spec, summary):
        return {
            "key": spec.key,
            "label": spec.label,
            "layer": spec.layer,
            "source": spec.source,
            "source_url": spec.source_url,
            "authority": spec.authority,
            "api_cost_usd": 0,
            "requires_api_key": False,
            "limitation": spec.limitation,
            "as_of": now,
            "metrics": {"signal": 1},
            "summary": summary,
        }

    result = intelligence.assemble_intelligence(
        [
            fixture(public, "public live"),
            RuntimeError("offline"),
            fixture(official, "official live"),
        ],
        [public, failed, official],
        ["core", "technology", "cyber"],
    )
    packet = intelligence.compact_intelligence_for_ai(result)

    assert [item["key"] for item in result["streams"]] == [
        "ecb_fx",
        "attention",
        "cyber_risk",
    ]
    assert [item["key"] for item in packet["evidence"]] == [
        "ecb_fx",
        "attention",
    ]
    assert packet["omitted_selected_sources"] == 1


@pytest.mark.asyncio
async def test_hacker_news_item_failure_is_isolated():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("topstories.json"):
            return httpx.Response(200, json=[1, 2, 3])
        if request.url.path.endswith("/2.json"):
            return httpx.Response(503, json={"error": "temporary"})
        story_id = int(request.url.path.rsplit("/", 1)[-1].split(".")[0])
        return httpx.Response(
            200,
            json={"title": f"story {story_id}", "score": story_id, "time": 1_720_000_000},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await intelligence._ingest_attention(client)

    assert result["metrics"]["top_story_count"] == 2
    assert "story 3" in result["summary"]


@pytest.mark.asyncio
async def test_world_bank_keeps_partial_indicators_when_one_request_fails():
    def handler(request: httpx.Request) -> httpx.Response:
        if "FP.CPI.TOTL.ZG" in request.url.path:
            return httpx.Response(503, json={"error": "temporary"})
        return httpx.Response(
            200,
            json=[{"page": 1}, [{"date": "2025", "value": 2.5}]],
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await intelligence._ingest_world_bank(client)

    assert result["as_of"] == "2025"
    assert len(result["metrics"]) == 2
    assert "global_inflation_pct" not in result["metrics"]


@pytest.mark.asyncio
async def test_eurostat_uses_ea21_first_and_records_real_period_with_fallback():
    requested_geographies: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        geo = str(request.url.params.get("geo"))
        requested_geographies.append(geo)
        if geo == "EA21":
            return httpx.Response(
                200,
                json={
                    "value": {},
                    "dimension": {"time": {"category": {"index": {}}}},
                },
            )
        return httpx.Response(
            200,
            json={
                "value": {"0": 2.1, "1": 2.0},
                "dimension": {
                    "time": {"category": {"index": {"2025-11": 0, "2025-12": 1}}},
                    "geo": {"category": {"label": {"EA20": "Euro area - 20 countries"}}},
                },
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await intelligence._ingest_eurostat(client)

    assert requested_geographies[:2] == ["EA21", "EA20"]
    assert result["metrics"]["aggregate_code"] == "EA20"
    assert result["metrics"]["current_aggregate"] is False
    assert result["as_of"] == "2025-12"


@pytest.mark.asyncio
async def test_treasury_requests_and_labels_the_bill_average_not_a_market_yield():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["filter"] == "security_desc:eq:Treasury Bills"
        assert request.url.params["page[size]"] == "1"
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "record_date": "2026-06-30",
                        "security_type_desc": "Marketable",
                        "security_desc": "Treasury Bills",
                        "avg_interest_rate_amt": "3.706",
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await intelligence._ingest_treasury(client)

    assert result["as_of"] == "2026-06-30"
    assert result["metrics"]["average_interest_rate_pct"] == 3.706
    assert "not a new-issue yield" in result["summary"]


@pytest.mark.asyncio
async def test_bls_names_series_and_calculates_same_month_cpi_yoy():
    year = datetime.now(timezone.utc).year

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "REQUEST_SUCCEEDED",
                "Results": {
                    "series": [
                        {
                            "seriesID": "CUUR0000SA0",
                            "data": [
                                {
                                    "year": str(year),
                                    "period": "M06",
                                    "periodName": "June",
                                    "value": "110",
                                },
                                {
                                    "year": str(year - 1),
                                    "period": "M06",
                                    "periodName": "June",
                                    "value": "100",
                                },
                            ],
                        },
                        {
                            "seriesID": "LNS14000000",
                            "data": [
                                {
                                    "year": str(year),
                                    "period": "M06",
                                    "periodName": "June",
                                    "value": "4.2",
                                }
                            ],
                        },
                    ]
                },
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await intelligence._ingest_us_labor(client)

    cpi = result["metrics"]["us_cpi_u_all_items_not_seasonally_adjusted"]
    unemployment = result["metrics"][
        "us_unemployment_rate_seasonally_adjusted_pct"
    ]
    assert cpi["year_over_year_pct"] == 10.0
    assert unemployment["value"] == 4.2
    assert result["as_of"] == f"{year}-06"


@pytest.mark.asyncio
async def test_cisa_recent_items_are_sorted_by_date_added():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "count": 3,
                "catalogVersion": "test",
                "dateReleased": "2026-07-10T17:00:25.7327Z",
                "vulnerabilities": [
                    {"cveID": "CVE-old", "vendorProject": "Old", "dateAdded": "2025-01-01"},
                    {"cveID": "CVE-new", "vendorProject": "New", "dateAdded": "2026-07-09"},
                    {"cveID": "CVE-mid", "vendorProject": "Mid", "dateAdded": "2026-01-01"},
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await intelligence._ingest_cyber(client)

    additions = result["metrics"]["recently_added"]
    assert [item["cve"] for item in additions] == [
        "CVE-new",
        "CVE-mid",
        "CVE-old",
    ]
    assert intelligence._parse_observation_time(result["as_of"]) is not None


@pytest.mark.asyncio
async def test_offline_mode_is_deterministic_and_performs_zero_fetches(monkeypatch):
    monkeypatch.setenv("OMNI_OFFLINE_MODE", "1")
    monkeypatch.setenv("OMNI_DEMO_MODE", "1")
    monkeypatch.setenv(intelligence.DEMO_NETWORK_OPT_IN_ENV, "1")
    fetches = 0
    clients = 0

    async def forbidden_fetch(*_args, **_kwargs):
        nonlocal fetches
        fetches += 1
        raise AssertionError("offline mode attempted a source fetch")

    def forbidden_client(*_args, **_kwargs):
        nonlocal clients
        clients += 1
        raise AssertionError("offline mode constructed an HTTP client")

    monkeypatch.setattr(intelligence, "_fetch_one", forbidden_fetch)
    monkeypatch.setattr(intelligence, "_BoundedAsyncClient", forbidden_client)

    first = await intelligence.gather_market_intelligence(
        "European Union cybersecurity tender opportunity", "B2B", "strategic"
    )
    second = await intelligence.gather_market_intelligence(
        "European Union cybersecurity tender opportunity", "B2B", "strategic"
    )

    assert first == second
    assert fetches == 0
    assert clients == 0
    assert first["mode"] == "offline"
    assert first["network_requests_made"] == 0
    assert first["cache_status"] == "bypassed"
    assert first["coverage_live"] == 0
    assert first["streams"]
    assert all(stream["status"] == "degraded" for stream in first["streams"])
    assert all(stream["cache"]["status"] == "bypassed" for stream in first["streams"])


@pytest.mark.asyncio
@pytest.mark.parametrize("demo_env", ["OMNI_DEMO_MODE", "OMNI_AI_DEMO_MODE"])
async def test_demo_modes_are_network_free_without_explicit_opt_in(
    monkeypatch, demo_env
):
    monkeypatch.delenv("OMNI_OFFLINE_MODE", raising=False)
    monkeypatch.delenv("OMNI_DEMO_MODE", raising=False)
    monkeypatch.delenv("OMNI_AI_DEMO_MODE", raising=False)
    monkeypatch.delenv(intelligence.DEMO_NETWORK_OPT_IN_ENV, raising=False)
    monkeypatch.setenv(demo_env, "true")
    fetches = 0
    clients = 0

    async def forbidden_fetch(*_args, **_kwargs):
        nonlocal fetches
        fetches += 1
        raise AssertionError("demo mode attempted a source fetch")

    def forbidden_client(*_args, **_kwargs):
        nonlocal clients
        clients += 1
        raise AssertionError("demo mode constructed an HTTP client")

    monkeypatch.setattr(intelligence, "_fetch_one", forbidden_fetch)
    monkeypatch.setattr(intelligence, "_BoundedAsyncClient", forbidden_client)

    result = await intelligence.gather_market_intelligence("bitcoin market", "B2C")

    assert fetches == 0
    assert clients == 0
    assert result["mode"] == "demo"
    assert result["degraded_reason"] == "demo_network_disabled"
    assert result["network_requests_made"] == 0
    assert all(stream["freshness"]["status"] == "not_fetched" for stream in result["streams"])


def test_demo_network_access_requires_the_named_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("OMNI_OFFLINE_MODE", raising=False)
    monkeypatch.setenv("OMNI_DEMO_MODE", "1")
    monkeypatch.setenv(intelligence.DEMO_NETWORK_OPT_IN_ENV, "yes")

    assert intelligence._network_disabled_mode() is None


@pytest.mark.asyncio
async def test_bounded_client_rejects_large_decoded_response(monkeypatch):
    monkeypatch.setattr(intelligence, "MAX_RESPONSE_BYTES", 16)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 17)

    async with intelligence._BoundedAsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(intelligence.SourceResponseTooLarge):
            await client.get("https://example.com/data")


@pytest.mark.asyncio
async def test_negative_cache_avoids_immediate_repeat_fetch():
    calls = 0

    async def fail(_client: httpx.AsyncClient):
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("offline")

    spec = intelligence._spec(
        "test_negative_cache",
        "Test",
        "test",
        "Test",
        "https://example.com/",
        fail,
        ("test",),
        30,
        60,
    )
    intelligence._SOURCE_CACHE.pop(spec.key, None)
    intelligence._SOURCE_FAILURES.pop(spec.key, None)
    async with httpx.AsyncClient() as client:
        with pytest.raises(httpx.ConnectError):
            await intelligence._fetch_one(client, spec)
        with pytest.raises(intelligence.SourceBackoffOpen):
            await intelligence._fetch_one(client, spec)

    assert calls == 1
    intelligence._SOURCE_FAILURES.pop(spec.key, None)
