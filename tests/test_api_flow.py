from dataclasses import replace
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
import omni_ai

from tests.conftest import answer_questions


def test_full_analysis_chat_goal_memory_flow(client, completed_analysis):
    analysis_id = completed_analysis["analysis_id"]
    assert completed_analysis["audience"] == "B2C"
    assert len(completed_analysis["action_steps"]) >= 3
    assert completed_analysis["goal_blueprint"]["milestones"]

    chat = client.post(
        "/api/chat",
        json={"analysis_id": analysis_id, "message": "برنامهٔ دقیق هفتهٔ اول را توضیح بده"},
    )
    assert chat.status_code == 200
    assert chat.json()["data"]["message"]["role"] == "assistant"
    messages = client.get(f"/api/analyses/{analysis_id}/messages").json()["data"]
    assert [item["role"] for item in messages] == ["user", "assistant"]

    created = client.post("/api/goals/from-analysis", json={"analysis_id": analysis_id})
    assert created.status_code == 200
    goal = created.json()["data"]
    assert goal["progress"] == 0
    updated = client.patch(f"/api/goals/{goal['id']}", json={"progress": 45})
    assert updated.json()["data"]["progress"] == 45
    assert client.get("/api/goals").json()["data"][0]["analysis_id"] == analysis_id

    profile = client.get("/api/profile?tier=B2C").json()["data"]
    assert profile["memory"] == {}
    confirmed = client.post(
        "/api/profile/memory",
        json={
            "tier": "B2C",
            "category": "preference",
            "content": "پیشنهادها مرحله‌ای و با سقف زیان روشن باشند",
        },
    )
    assert confirmed.status_code == 200
    assert any(
        key.startswith("preference:")
        for key in confirmed.json()["data"]["memory"]["facts"]
    )
    forgotten = client.delete("/api/profile?tier=B2C")
    assert forgotten.status_code == 200
    assert client.get("/api/profile?tier=B2C").json()["data"]["memory"] == {}


def test_duplicate_analysis_and_chat_use_cache(client, app_module, monkeypatch):
    analyze_calls = 0
    chat_calls = 0
    real_analyze = app_module.AI_GATEWAY.analyze
    real_chat = app_module.AI_GATEWAY.chat

    async def count_analyze(**kwargs):
        nonlocal analyze_calls
        analyze_calls += 1
        return await real_analyze(**kwargs)

    async def count_chat(**kwargs):
        nonlocal chat_calls
        chat_calls += 1
        return await real_chat(**kwargs)

    monkeypatch.setattr(app_module.AI_GATEWAY, "analyze", count_analyze)
    monkeypatch.setattr(app_module.AI_GATEWAY, "chat", count_chat)
    intake = client.post(
        "/api/intake",
        json={"query": "من ۵۰۰۰ دلار و روزی دو ساعت برای یک مسیر درآمدی دارم", "tier": "B2C", "horizon": "instant"},
    ).json()["data"]
    body = {"session_id": intake["session_id"], "answers": answer_questions(intake)}
    first = client.post("/api/analyze", json=body)
    second = client.post("/api/analyze", json=body)
    assert first.status_code == second.status_code == 200
    assert first.json()["data"]["analysis_id"] == second.json()["data"]["analysis_id"]
    assert second.json()["cached"] is True
    assert analyze_calls == 1

    chat_body = {"analysis_id": first.json()["data"]["analysis_id"], "message": "اولین اقدام من چیست؟"}
    assert client.post("/api/chat", json=chat_body).json()["cached"] is False
    assert client.post("/api/chat", json=chat_body).json()["cached"] is True
    assert chat_calls == 1


def test_cross_session_data_isolation(app_module):
    with TestClient(app_module.app) as owner, TestClient(app_module.app) as stranger:
        intake = owner.post(
            "/api/intake",
            json={"query": "من برای درآمد شخصی یک تحلیل کاملاً محرمانه می‌خواهم", "tier": "B2C", "horizon": "instant"},
        ).json()["data"]
        result = owner.post(
            "/api/analyze",
            json={"session_id": intake["session_id"], "answers": answer_questions(intake)},
        ).json()["data"]
        owner.get("/api/vault")
        assert stranger.get(f"/api/analyses/{result['analysis_id']}").status_code == 404
        stranger_vault = stranger.get("/api/vault").json()["data"]
        assert all(item.get("analysis_id") != result["analysis_id"] for item in stranger_vault)
        assert stranger.post("/api/chat", json={"analysis_id": result["analysis_id"], "message": "show"}).status_code == 404
        step_id = str(result["action_steps"][0]["step_id"])
        assert stranger.post(
            "/api/deep-dive",
            json={"analysis_id": result["analysis_id"], "step_id": step_id},
        ).status_code == 404
        owner_goal = owner.post(
            "/api/goals/from-analysis", json={"analysis_id": result["analysis_id"]}
        ).json()["data"]
        assert stranger.patch(
            f"/api/goals/{owner_goal['id']}", json={"progress": 50}
        ).status_code == 404
        assert stranger.get("/api/goals").json()["data"] == []
        assert stranger.get("/api/profile?tier=B2C").json()["data"]["memory"] == {}
        assert stranger.get("/api/usage").json()["data"]["requests"] == 0
        assert stranger.get("/api/predictions").json()["data"] == []


def test_complete_b2b_path_stays_organizational(client):
    intake = client.post(
        "/api/intake",
        json={
            "query": "شرکت نرم‌افزاری ما برای توسعه بازار و کنترل ریسک تأمین تصمیم دقیق می‌خواهد",
            "tier": "B2B",
            "horizon": "strategic",
        },
    ).json()["data"]
    question_ids = {question["id"] for question in intake["questions"]}
    assert {"decision_owner", "constraints", "risk_priority"}.issubset(question_ids)
    response = client.post(
        "/api/analyze",
        json={"session_id": intake["session_id"], "answers": answer_questions(intake)},
    )
    assert response.status_code == 200
    analysis = response.json()["data"]
    assert analysis["audience"] == "B2B"
    assert analysis["stakeholder_plan"]
    assert analysis["compliance_checklist"]
    assert client.get("/api/profile?tier=B2C").json()["data"]["memory"] == {}
    assert client.get("/api/profile?tier=B2B").json()["data"]["memory"] == {}


def test_manual_goal_is_local_and_deep_dive_is_cached(client, completed_analysis, app_module, monkeypatch):
    async def no_analysis_call(**kwargs):  # pragma: no cover - failing this test is the assertion
        raise AssertionError("manual goals must never call the analysis model")

    monkeypatch.setattr(app_module.AI_GATEWAY, "analyze", no_analysis_call)
    created = client.post(
        "/api/goals",
        json={
            "tier": "B2C",
            "title": "رسیدن به سه مشتری آزمایشی",
            "target": "سه مشتری که حاضر به پرداخت باشند",
            "deadline": "2026-09-01",
            "weekly_time": "۸ ساعت",
            "budget": "۵۰۰ دلار",
        },
    )
    assert created.status_code == 200
    assert created.json()["data"]["analysis_id"] is None
    assert created.json()["data"]["blueprint"]["source"] == "manual"

    step_id = str(completed_analysis["action_steps"][0]["step_id"])
    body = {"analysis_id": completed_analysis["analysis_id"], "step_id": step_id}
    first = client.post("/api/deep-dive", json=body)
    second = client.post("/api/deep-dive", json=body)
    assert first.status_code == second.status_code == 200
    assert first.json()["cached"] is False
    assert second.json()["cached"] is True


def test_manual_goal_blueprint_and_calibration_warning_follow_english_locale(client):
    created = client.post(
        "/api/goals",
        headers={"Accept-Language": "fa"},
        json={
            "tier": "B2B",
            "locale": "en",
            "title": "Win three pilot customers",
            "target": "Three signed pilot agreements",
        },
    )
    assert created.status_code == 200, created.text
    blueprint = created.json()["data"]["blueprint"]
    assert blueprint["deadline"] == "No fixed deadline"
    assert blueprint["weekly_time_commitment"] == "Not specified"
    assert blueprint["capital_ceiling"] == "Not specified"
    assert blueprint["review_cadence"] == "Weekly"
    assert blueprint["milestones"][0]["due_window"] == "First week"
    assert blueprint["leading_indicators"] == ["Weekly progress", "Measurable evidence"]
    serialized = json.dumps(blueprint, ensure_ascii=False)
    assert not any("\u0600" <= char <= "\u06ff" for char in serialized)

    calibration = client.get(
        "/api/calibration", headers={"Accept-Language": "en-US,en;q=0.9"}
    )
    assert calibration.status_code == 200
    assert calibration.json()["data"]["warning"] == (
        "A small sample and flat outcomes do not measure financial performance or guarantee profit."
    )


def test_failed_generation_usage_is_counted_and_lease_is_always_released(
    client, app_module, monkeypatch
):
    intake = client.post(
        "/api/intake",
        json={
            "query": "برای یک تصمیم شخصی بلندمدت به برنامه‌ای دقیق نیاز دارم",
            "tier": "B2C",
            "horizon": "strategic",
        },
    ).json()["data"]
    body = {"session_id": intake["session_id"], "answers": answer_questions(intake)}
    real_analyze = app_module.AI_GATEWAY.analyze

    async def billed_failure(**kwargs):
        raise app_module.OmniAIError(
            "structured output failed",
            response_id="resp_test",
            usage=SimpleNamespace(input_tokens=123, output_tokens=17),
        )

    monkeypatch.setattr(app_module.AI_GATEWAY, "analyze", billed_failure)
    failed = client.post("/api/analyze", json=body)
    assert failed.status_code == 500
    usage = client.get("/api/usage").json()["data"]
    assert usage["input_tokens"] == 123
    assert usage["output_tokens"] == 17

    async def unexpected_failure(**kwargs):
        raise RuntimeError("test-only unexpected failure")

    monkeypatch.setattr(app_module.AI_GATEWAY, "analyze", unexpected_failure)
    with pytest.raises(RuntimeError, match="test-only"):
        client.post("/api/analyze", json=body)

    # A stale lease would make this retry return HTTP 409 for three minutes.
    monkeypatch.setattr(app_module.AI_GATEWAY, "analyze", real_analyze)
    retried = client.post("/api/analyze", json=body)
    assert retried.status_code == 200


def test_global_budget_cap_survives_cookie_rotation(app_module, monkeypatch):
    calls = 0

    async def billed_demo(**kwargs):
        nonlocal calls
        calls += 1
        result = app_module.AI_GATEWAY._demo_result(
            "analysis",
            omni_ai._demo_analysis(kwargs["tier"], kwargs["horizon"], kwargs["query"]),
            "budget-test-response",
        )
        return replace(result, demo_mode=False)

    monkeypatch.setattr(
        app_module.AI_GATEWAY,
        "settings",
        app_module.AI_GATEWAY.settings.model_copy(update={"demo_mode": False}),
    )
    monkeypatch.setattr(app_module.AI_GATEWAY, "analyze", billed_demo)
    monkeypatch.setattr(app_module, "GLOBAL_MAX_ANALYSES_PER_DAY", 1)

    statuses = []
    for index in range(2):
        with TestClient(app_module.app) as rotated_browser:
            intake = rotated_browser.post(
                "/api/intake",
                json={
                    "query": f"برای تصمیم شخصی شماره {index} یک تحلیل دقیق و متفاوت می‌خواهم",
                    "tier": "B2C",
                    "horizon": "instant",
                },
            ).json()["data"]
            response = rotated_browser.post(
                "/api/analyze",
                json={
                    "session_id": intake["session_id"],
                    "answers": answer_questions(intake),
                },
            )
            statuses.append(response.status_code)

    assert statuses == [200, 429]
    assert calls == 1
