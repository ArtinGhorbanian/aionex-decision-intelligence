def test_clarification_is_zero_cost_and_does_not_repeat_known_facts(client, app_module, monkeypatch):
    calls = 0
    original = app_module.AI_GATEWAY.analyze

    async def counted(**kwargs):
        nonlocal calls
        calls += 1
        return await original(**kwargs)

    monkeypatch.setattr(app_module.AI_GATEWAY, "analyze", counted)
    response = client.post(
        "/api/intake",
        json={
            "query": "من ۵ هزار دلار دارم و روزی ۲ ساعت وقت آزاد دارم؛ بهترین مسیر امن چیست؟",
            "tier": "B2C",
            "horizon": "strategic",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    ids = {question["id"] for question in data["questions"]}
    assert "capital_range" not in ids
    assert "available_time" not in ids
    assert data["known_facts"]["capital"] == "5 هزار دلار"
    assert data["model_calls"] == 0
    assert calls == 0
    assert client.get("/api/usage").json()["data"]["requests"] == 0


def test_b2c_and_b2b_have_different_decision_workflows(client):
    b2c = client.post(
        "/api/intake",
        json={"query": "برای افزایش درآمد شخصی یک مسیر دقیق می‌خواهم", "tier": "B2C", "horizon": "instant"},
    ).json()["data"]
    b2b = client.post(
        "/api/intake",
        json={"query": "برای کاهش ریسک تأمین سازمان یک تحلیل دقیق می‌خواهیم", "tier": "B2B", "horizon": "instant"},
    ).json()["data"]
    b2c_ids = {item["id"] for item in b2c["questions"]}
    b2b_ids = {item["id"] for item in b2b["questions"]}
    assert "skills" in b2c_ids
    assert "decision_owner" in b2b_ids
    assert b2c_ids != b2b_ids


def test_strategic_horizon_prioritizes_validation_and_enterprise_downside(client):
    instant = client.post(
        "/api/intake",
        json={"query": "برای درآمد شخصی یک تصمیم دقیق می‌خواهم", "tier": "B2C", "horizon": "instant"},
    ).json()["data"]
    strategic = client.post(
        "/api/intake",
        json={"query": "برای درآمد شخصی یک تصمیم دقیق می‌خواهم", "tier": "B2C", "horizon": "strategic"},
    ).json()["data"]
    instant_ids = [item["id"] for item in instant["questions"]]
    strategic_ids = [item["id"] for item in strategic["questions"]]
    assert instant_ids != strategic_ids
    assert "validation_style" in strategic_ids

    b2b = client.post(
        "/api/intake",
        json={
            "query": "برای کاهش ریسک یک تصمیم سازمانی بلندمدت لازم داریم",
            "tier": "B2B",
            "horizon": "strategic",
        },
    ).json()["data"]
    b2b_ids = {item["id"] for item in b2b["questions"]}
    assert {"constraints", "risk_priority"}.issubset(b2b_ids)


def test_analysis_requires_every_issued_answer(client):
    intake = client.post(
        "/api/intake",
        json={"query": "یک کسب‌وکار شخصی کم‌ریسک برای من طراحی کن", "tier": "B2C", "horizon": "instant"},
    ).json()["data"]
    response = client.post("/api/analyze", json={"session_id": intake["session_id"], "answers": {}})
    assert response.status_code == 422


def test_invalid_tier_and_short_query_are_rejected(client):
    assert client.post("/api/intake", json={"query": "valid long query", "tier": "OTHER"}).status_code == 422
    assert client.post("/api/intake", json={"query": "short", "tier": "B2C"}).status_code == 422


def test_only_confirmed_memory_reuses_skills_and_rechecks_volatile_facts(
    client, completed_analysis
):
    assert completed_analysis["analysis_id"]
    profile = client.get("/api/profile?tier=B2C").json()["data"]
    assert profile["memory"] == {}

    unconfirmed_intake = client.post(
        "/api/intake",
        json={
            "query": "برای تصمیم شخصی بعدی من یک مسیر تازه و دقیق طراحی کن",
            "tier": "B2C",
            "horizon": "instant",
        },
    ).json()["data"]
    assert "skills" in {question["id"] for question in unconfirmed_intake["questions"]}

    confirmed = client.post(
        "/api/profile/memory",
        json={
            "tier": "B2C",
            "category": "skill",
            "content": "Market research and consultative sales",
        },
    )
    assert confirmed.status_code == 200

    next_intake = client.post(
        "/api/intake",
        json={
            "query": "برای تصمیم شخصی بعدی من یک مسیر تازه و دقیق طراحی کن",
            "tier": "B2C",
            "horizon": "instant",
        },
    ).json()["data"]
    ids = {question["id"] for question in next_intake["questions"]}
    assert "skills" not in ids
    assert "capital_range" in ids
    assert "available_time" in ids


def test_explicit_unknown_is_valid_but_never_becomes_long_term_memory(client):
    intake = client.post(
        "/api/intake",
        json={
            "query": "برای یک مسیر درآمدی شخصی به تحلیل دقیق نیاز دارم",
            "tier": "B2C",
            "horizon": "instant",
        },
    ).json()["data"]
    answers = {question["id"]: "unknown" for question in intake["questions"]}
    result = client.post(
        "/api/analyze",
        json={"session_id": intake["session_id"], "answers": answers},
    )
    assert result.status_code == 200
    profile = client.get("/api/profile?tier=B2C").json()["data"]
    assert "skills" not in profile["memory"].get("facts", {})

    next_intake = client.post(
        "/api/intake",
        json={
            "query": "برای تصمیم شخصی تازه‌ای دوباره تحلیل دقیق می‌خواهم",
            "tier": "B2C",
            "horizon": "instant",
        },
    ).json()["data"]
    assert "skills" in {question["id"] for question in next_intake["questions"]}
