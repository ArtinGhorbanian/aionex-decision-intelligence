from __future__ import annotations

import json

from tests.conftest import answer_questions


def test_confidence_requires_multiple_external_sources(app_module):
    one_source = app_module.enforce_confidence_integrity("High", 1, 1)
    assert one_source["confidence"] == "Low"
    assert one_source["capped"] is True
    assert "External evidence is limited" in one_source["evidence_note"]

    two_sources = app_module.enforce_confidence_integrity("High", 2, 2)
    assert two_sources["confidence"] == "Moderate"
    assert two_sources["capped"] is True

    three_sources = app_module.enforce_confidence_integrity("High", 3, 3)
    assert three_sources["confidence"] == "High"
    assert three_sources["capped"] is False


def test_confidence_counts_independent_usable_providers_not_weighted_streams(app_module):
    intelligence = {
        "coverage_live": 3.9,
        "coverage_total": 4,
        "streams": [
            {
                "key": "one",
                "status": "live",
                "source_url": "https://api.example.test/one",
                "source": "Provider A",
                "summary": "usable one",
            },
            {
                "key": "two",
                "status": "partial",
                "source_url": "https://api.example.test/two",
                "source": "Provider A",
                "summary": "usable two from the same provider",
            },
            {
                "key": "three",
                "status": "stale",
                "source_url": "https://evidence.example.org/data",
                "source": "Provider B",
                "summary": "usable stale fallback",
            },
            {
                "key": "four",
                "status": "degraded",
                "source_url": "https://third.example.net/data",
                "source": "Provider C",
                "summary": "must not count",
            },
        ],
    }

    usable = app_module._usable_independent_source_count(intelligence)
    assert usable == 2
    integrity = app_module.enforce_confidence_integrity("High", usable, 4)
    assert integrity["confidence"] == "Moderate"
    assert "2/4 independent usable sources" in integrity["evidence_note"]


def test_prediction_baseline_accepts_direct_ecb_stream(app_module):
    value, source = app_module.extract_metric_baseline(
        {
            "streams": [
                {
                    "key": "ecb_fx",
                    "status": "live",
                    "metrics": {"eur_usd_reference": 1.1724},
                }
            ]
        },
        "eur_usd",
    )
    assert value == 1.1724
    assert source == "European Central Bank"


def _analyze(
    client,
    query: str = "Build a software consulting income path with a limited budget",
    locale: str = "fa",
):
    intake = client.post(
        "/api/intake",
        json={
            "query": query,
            "tier": "B2C",
            "horizon": "instant",
            "locale": locale,
        },
    ).json()["data"]
    answers = answer_questions(intake)
    response = client.post(
        "/api/analyze",
        json={
            "session_id": intake["session_id"],
            "answers": answers,
            "locale": locale,
        },
    )
    assert response.status_code == 200, response.text
    return intake, answers, response.json()


def test_sparse_external_evidence_is_explained_in_analysis_reason(
    client, app_module, monkeypatch
):
    async def sparse_intelligence(*_args, **_kwargs):
        return {
            "coverage_live": 1,
            "coverage_total": 1,
            "coverage_label": "1/1",
            "captured_at": "2026-07-13T00:00:00Z",
            "streams": [
                {
                    "key": "ecb_fx",
                    "label": "ECB FX",
                    "status": "live",
                    "completeness": 1,
                    "source": "European Central Bank",
                    "metrics": {"eur_usd_reference": 1.1724},
                    "summary": "ECB reference rate",
                }
            ],
        }

    monkeypatch.setattr(app_module, "gather_market_intelligence", sparse_intelligence)
    _, _, result = _analyze(client, locale="en")
    analysis = result["data"]
    assert analysis["confidence"] == "Low"
    assert "External evidence remains limited" in analysis["confidence_reason"]


def test_analysis_router_uses_answers_and_memory_without_changing_cache_calls(
    client, app_module, monkeypatch
):
    query = "Build a cybersecurity consulting income path for small businesses"
    intake = client.post(
        "/api/intake",
        json={"query": query, "tier": "B2C", "horizon": "instant"},
    ).json()["data"]
    answers = answer_questions(intake)
    memory_fact = "I have hands-on Rust and security-audit experience"
    assert client.post(
        "/api/profile/memory",
        json={"tier": "B2C", "category": "skill", "content": memory_fact},
    ).status_code == 200

    captured_contexts: list[str] = []
    gather = app_module.gather_market_intelligence
    analyze = app_module.AI_GATEWAY.analyze
    analyze_calls = 0

    async def capture_gather(*, query, tier, horizon, routing_context):
        captured_contexts.append(routing_context)
        return await gather(query=query, tier=tier, horizon=horizon)

    async def count_analyze(**kwargs):
        nonlocal analyze_calls
        analyze_calls += 1
        return await analyze(**kwargs)

    monkeypatch.setattr(app_module, "gather_market_intelligence", capture_gather)
    monkeypatch.setattr(app_module.AI_GATEWAY, "analyze", count_analyze)
    body = {"session_id": intake["session_id"], "answers": answers}
    first = client.post("/api/analyze", json=body)
    second = client.post("/api/analyze", json=body)

    assert first.status_code == second.status_code == 200
    assert second.json()["cached"] is True
    assert analyze_calls == 1
    assert len(captured_contexts) == 1
    routing_context = captured_contexts[0]
    assert query in routing_context
    assert memory_fact in routing_context
    assert any(value in routing_context for value in answers.values())
    stored = app_module.store.get_analysis(first.json()["data"]["analysis_id"])
    assert "execution_kit" not in stored["data"]


def test_get_rebuilds_and_vault_strips_stale_kit_in_accept_language(
    client, app_module, monkeypatch
):
    _, _, analyzed = _analyze(client)
    analysis_id = analyzed["data"]["analysis_id"]
    real_get = app_module.store.get_analysis
    real_list = app_module.store.list_analyses
    kit_calls: list[tuple[str, str]] = []

    def add_stale_kit(row):
        if not row:
            return row
        stale = dict(row)
        stale["data"] = dict(row["data"])
        stale["data"]["execution_kit"] = {
            "locale": "fa",
            "resources": [{"url": "javascript:unsafe"}],
        }
        stale["intelligence"] = dict(row["intelligence"])
        stale["intelligence"]["source_catalog"] = [{"raw": "x" * 10_000}]
        return stale

    def stale_get(row_id, client_id=None):
        return add_stale_kit(real_get(row_id, client_id))

    def stale_list(client_id, limit=30, include_legacy=False):
        return [
            add_stale_kit(row)
            for row in real_list(client_id, limit, include_legacy)
        ]

    def local_kit(
        query,
        tier,
        lang_code="fa",
        action_steps=None,
        *,
        context=None,
        facts=None,
        locale=None,
    ):
        kit_calls.append((context or query, locale or lang_code))
        return {
            "locale": locale or lang_code,
            "resources": [{"url": "https://example.com/safe"}],
            "additional_model_calls": 0,
        }

    monkeypatch.setattr(app_module.store, "get_analysis", stale_get)
    monkeypatch.setattr(app_module.store, "list_analyses", stale_list)
    monkeypatch.setattr(app_module, "build_execution_kit", local_kit)

    headers = {"Accept-Language": "en-US,en;q=0.9"}
    fetched = client.get(f"/api/analyses/{analysis_id}", headers=headers)
    vault = client.get("/api/vault", headers=headers)
    assert fetched.status_code == vault.status_code == 200
    assert fetched.json()["data"]["execution_kit"]["locale"] == "en"
    vault_item = vault.json()["data"][0]
    assert "execution_kit" not in vault_item
    assert vault_item["response_locale"] == "en"
    assert vault_item["detail_available"] is True
    assert vault_item["summary_version"] == 1
    assert "executive_summary" not in vault_item
    assert "action_steps" not in vault_item
    assert "goal_blueprint" not in vault_item
    assert "risk_assessment" not in vault_item
    assert all(call[1] == "en" for call in kit_calls)
    assert "source_catalog" not in vault_item["intelligence_snapshot"]
    assert all(
        "metrics" not in stream
        for stream in vault_item["intelligence_snapshot"]["streams"]
    )
    assert len(json.dumps(vault_item, ensure_ascii=False)) < 12_000


def test_english_legacy_analysis_goal_fallback_contains_no_persian(
    client, app_module, monkeypatch
):
    _, _, analyzed = _analyze(client, locale="en")
    analysis_id = analyzed["data"]["analysis_id"]
    real_get = app_module.store.get_analysis

    def legacy_get(row_id, client_id=None):
        row = real_get(row_id, client_id)
        if row and row_id == analysis_id:
            row = dict(row)
            row["data"] = dict(row["data"])
            row["data"].pop("goal_blueprint", None)
            row["data"]["action_steps"] = []
        return row

    monkeypatch.setattr(app_module.store, "get_analysis", legacy_get)
    response = client.post(
        "/api/goals/from-analysis",
        headers={"Accept-Language": "en"},
        json={"analysis_id": analysis_id, "locale": "en"},
    )
    assert response.status_code == 200, response.text
    goal = response.json()["data"]
    serialized = json.dumps(goal, ensure_ascii=False)
    assert not any("\u0600" <= character <= "\u06ff" for character in serialized)
    assert goal["blueprint"]["goal_title"] == analyzed["data"]["signal_name"]
    assert goal["blueprint"]["milestones"][0]["title"] == "Staged validation"


def test_chat_and_deep_cached_kits_use_full_context_and_are_not_persisted(
    client, app_module, monkeypatch
):
    query = "Plan a B2C software service for independent medical clinics"
    _, _, analyzed = _analyze(client, query)
    analysis = analyzed["data"]
    analysis_id = analysis["analysis_id"]
    memory_fact = "My preferred niche is clinic procurement automation"
    assert client.post(
        "/api/profile/memory",
        json={"tier": "B2C", "category": "preference", "content": memory_fact},
    ).status_code == 200

    kit_contexts: list[str] = []
    chat_model = app_module.AI_GATEWAY.chat
    deep_model = app_module.AI_GATEWAY.deep_dive
    chat_calls = 0
    deep_calls = 0

    def local_kit(
        query,
        tier,
        lang_code="fa",
        action_steps=None,
        *,
        context=None,
        facts=None,
        locale=None,
    ):
        kit_contexts.append(context or query)
        return {
            "locale": locale or lang_code,
            "additional_model_calls": 0,
            "resources": [],
        }

    async def count_chat(**kwargs):
        nonlocal chat_calls
        chat_calls += 1
        return await chat_model(**kwargs)

    async def count_deep(**kwargs):
        nonlocal deep_calls
        deep_calls += 1
        return await deep_model(**kwargs)

    monkeypatch.setattr(app_module, "build_execution_kit", local_kit)
    monkeypatch.setattr(app_module.AI_GATEWAY, "chat", count_chat)
    monkeypatch.setattr(app_module.AI_GATEWAY, "deep_dive", count_deep)

    message = "Give me the exact first outreach action for clinic buyers"
    chat_body = {"analysis_id": analysis_id, "message": message}
    first_chat = client.post("/api/chat", json=chat_body)
    second_chat = client.post("/api/chat", json=chat_body)
    assert first_chat.status_code == second_chat.status_code == 200
    assert first_chat.json()["cached"] is False
    assert second_chat.json()["cached"] is True
    assert chat_calls == 1

    step = analysis["action_steps"][0]
    deep_body = {"analysis_id": analysis_id, "step_id": str(step["step_id"])}
    first_deep = client.post("/api/deep-dive", json=deep_body)
    second_deep = client.post("/api/deep-dive", json=deep_body)
    assert first_deep.status_code == second_deep.status_code == 200
    assert first_deep.json()["cached"] is False
    assert second_deep.json()["cached"] is True
    assert deep_calls == 1

    row = app_module.store.get_analysis(analysis_id)
    answer_value = next(iter(row["answers"].values()))
    chat_contexts = [context for context in kit_contexts if message in context]
    assert chat_contexts
    assert all(query in context for context in chat_contexts)
    assert all(memory_fact in context for context in chat_contexts)
    assert all(answer_value in context for context in chat_contexts)
    assert any(str(step["title"]) in context for context in kit_contexts)

    with app_module.store.connection() as db:
        cached_rows = db.execute("SELECT response_json FROM deep_dive_cache").fetchall()
    assert len(cached_rows) == 2
    assert all("execution_kit" not in json.loads(item["response_json"]) for item in cached_rows)
