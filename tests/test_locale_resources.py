from __future__ import annotations

import json
import re
from dataclasses import replace

import pytest

from tests.conftest import answer_questions

import omni_resources


PERSIAN_RE = re.compile(r"[\u0600-\u06ff]")


def test_resource_catalog_is_safe_cost_disclosed_and_bilingual():
    omni_resources.validate_resource_catalog()
    assert len(omni_resources.RESOURCE_CATALOG) >= 12
    assert len({item.resource_id for item in omni_resources.RESOURCE_CATALOG}) == len(
        omni_resources.RESOURCE_CATALOG
    )
    for resource in omni_resources.RESOURCE_CATALOG:
        assert resource.url.startswith("https://")
        assert resource.access_type in omni_resources.ACCESS_TYPES
        assert resource.free_access is (
            resource.access_type in {"free_keyless", "free_account"}
        )
        assert resource.name.fa and resource.name.en
        assert resource.purpose.fa and resource.purpose.en
        assert resource.verified_at <= resource.review_after
        assert omni_resources.is_allowlisted_resource_url(resource.url)
        if resource.support_url:
            assert omni_resources.is_allowlisted_resource_url(resource.support_url)

    upwork = omni_resources.RESOURCE_BY_ID["upwork_profile"]
    assert upwork.access_type == "transaction_fee"
    assert upwork.free_access is False


def test_execution_kit_is_local_actionable_and_never_auto_sends():
    kit = omni_resources.build_execution_kit(
        "Our software supplier needs a security and procurement review",
        "B2B",
        "en",
        [{"title": "Validate vendor controls"}],
    )
    assert kit["generated_without_ai_call"] is True
    assert kit["additional_model_calls"] == 0
    assert kit["external_api_cost_usd"] == 0
    assert len(kit["first_24_hours"]) == 4
    assert 2 <= len(kit["resources"]) <= 6
    assert all(item["url"].startswith("https://") for item in kit["resources"])
    assert all(item["free_access"] is True for item in kit["resources"])
    assert all(
        item["access_type"] in {"free_keyless", "free_account"}
        for item in kit["resources"]
    )
    assert all(template["auto_send"] is False for template in kit["outreach_templates"])
    assert all(
        not PERSIAN_RE.search(template["body"])
        for template in kit["outreach_templates"]
    )


def test_boundary_matcher_does_not_read_ai_inside_email():
    tags = omni_resources.infer_resource_tags(
        "Send an email newsletter campaign", "B2C"
    )
    assert {"content", "marketing"} <= tags
    assert "technology" not in tags
    assert "cyber" not in tags


def test_nontechnical_sales_validation_excludes_developer_resources():
    kit = omni_resources.build_execution_kit(
        "Validate a sales offer for Canadian clients with customer interviews.",
        "B2C",
        "en",
        facts={"skills": "sales and market research", "market_access": "Canada"},
    )
    selected = {item["resource_id"] for item in kit["resources"]}
    assert "github_new_repo" not in selected
    assert "microsoft_learn" not in selected
    assert selected <= {"google_trends", "hubspot_academy", "world_bank_data"}


@pytest.mark.parametrize(
    ("query", "expected_resource"),
    [
        ("Create a GitHub repository for my prototype", "github_new_repo"),
        ("I want to take Microsoft Learn courses", "microsoft_learn"),
        ("برای نمونه کارم یک مخزن گیت‌هاب بسازم", "github_new_repo"),
        ("می‌خواهم دوره‌های مایکروسافت لرن را شروع کنم", "microsoft_learn"),
    ],
)
def test_explicit_bilingual_resource_names_select_the_named_resource(
    query, expected_resource
):
    kit = omni_resources.build_execution_kit(query, "B2C", "fa")
    selected = [item["resource_id"] for item in kit["resources"]]
    assert selected[0] == expected_resource


def test_explicit_resource_aliases_use_phrase_boundaries():
    explicit = omni_resources.infer_explicit_resource_ids(
        "Compare GitHubber repositories with Microsoft Learner courses"
    )
    assert explicit == set()


def test_australia_hr_uses_local_jurisdiction_from_structured_context():
    kit = omni_resources.build_execution_kit(
        "Review our HR employment policy",
        "B2B",
        "en",
        context={"profile": {"country_code": "AU"}},
    )
    assert kit["target_jurisdictions"] == ["AU"]
    assert kit["resources"][0]["resource_id"] == "australia_fair_work"
    assert all(item["jurisdiction"] in {"GLOBAL", "AU"} for item in kit["resources"])
    assert "US" not in {item["jurisdiction"] for item in kit["resources"]}
    assert [item["template_id"] for item in kit["outreach_templates"]] == [
        "workplace_rule_clarification"
    ]


def test_iran_factory_uses_global_industry_source_without_foreign_law():
    kit = omni_resources.build_execution_kit(
        "Compare suppliers for a new manufacturing factory",
        "B2B",
        "en",
        context={"jurisdiction": "IR"},
    )
    resource_ids = {item["resource_id"] for item in kit["resources"]}
    assert "unido_statistics" in resource_ids
    assert all(item["jurisdiction"] in {"GLOBAL", "IR"} for item in kit["resources"])
    assert [item["template_id"] for item in kit["outreach_templates"]] == [
        "supplier_rfq"
    ]


def test_canada_nursing_selects_credentials_and_not_us_health_rules():
    kit = omni_resources.build_execution_kit(
        "Plan the credential and employment route",
        "B2C",
        "en",
        facts={"target_country": "Canada", "profession": "registered nurse"},
    )
    resource_ids = {item["resource_id"] for item in kit["resources"]}
    assert "canada_foreign_credentials" in resource_ids
    assert "openfda" not in resource_ids
    assert all(item["jurisdiction"] in {"GLOBAL", "CA"} for item in kit["resources"])
    template = kit["outreach_templates"][0]
    assert template["template_id"] == "credential_requirements_request"
    assert template["source_resource_id"] == "canada_foreign_credentials"
    placeholders = set(
        re.findall(
            r"\[[^\[\]\r\n]{1,80}\]", f"{template['subject']}\n{template['body']}"
        )
    )
    assert set(template["customize_fields"]) == placeholders


def test_fee_resources_are_disclosed_but_never_recommended_by_default():
    kit = omni_resources.build_execution_kit(
        "Create an Upwork freelance profile and find clients", "B2C", "en"
    )
    assert "upwork_profile" not in {item["resource_id"] for item in kit["resources"]}
    assert kit["selection_policy"]["recommended_access_types"] == [
        "free_keyless",
        "free_account",
    ]
    assert "transaction_fee" in kit["selection_policy"]["excluded_access_types"]
    assert kit["external_api_calls"] == 0
    assert kit["query_shared_with_resources"] is False


@pytest.mark.parametrize(
    "url",
    [
        "https://www.sba.gov.evil.example/business-guide",
        "https://127.0.0.1/resource",
        "https://10.0.0.8/resource",
        "https://www.sba.gov:444/business-guide",
        "http://www.sba.gov/business-guide",
        "https://user:pass@www.sba.gov/business-guide",
    ],
)
def test_resource_urls_require_exact_allowlisted_host_without_ip_or_port(url):
    assert omni_resources.is_allowlisted_resource_url(url) is False
    bad = replace(omni_resources.RESOURCE_CATALOG[0], url=url)
    with pytest.raises(RuntimeError):
        omni_resources.validate_resource_catalog((bad,))


def test_outreach_is_intent_and_resource_driven_not_tier_driven():
    email_kit = omni_resources.build_execution_kit(
        "Plan an email newsletter campaign", "B2C", "en"
    )
    assert email_kit["outreach_templates"] == []

    generic_b2b = omni_resources.build_execution_kit(
        "Summarize the current exchange rate", "B2B", "en"
    )
    assert generic_b2b["outreach_templates"] == []

    assert omni_resources.build_outreach_templates("B2B", "en") == []


def test_english_locale_controls_intake_analysis_chat_and_deep_dive(client, app_module):
    intake_response = client.post(
        "/api/intake",
        json={
            "query": "من برای یک مسیر درآمدی نرم‌افزاری برنامه دقیق می‌خواهم",
            "tier": "B2C",
            "horizon": "instant",
            "locale": "en",
        },
        headers={"Accept-Language": "en"},
    )
    assert intake_response.status_code == 200
    intake = intake_response.json()["data"]
    assert intake["locale"] == "en"
    for question in intake["questions"]:
        assert not PERSIAN_RE.search(question["prompt"])
        assert not PERSIAN_RE.search(question["help"])
        assert all(
            not PERSIAN_RE.search(option["label"])
            for option in question.get("options", [])
        )

    analyzed = client.post(
        "/api/analyze",
        json={
            "session_id": intake["session_id"],
            "answers": answer_questions(intake),
            "locale": "en",
        },
        headers={"Accept-Language": "en"},
    )
    assert analyzed.status_code == 200
    analysis = analyzed.json()["data"]
    assert analysis["lang_code"] == "en"
    assert analysis["lang_dir"] == "ltr"
    assert not PERSIAN_RE.search(analysis["executive_summary"])
    assert analysis["execution_kit"]["additional_model_calls"] == 0
    assert all(
        not PERSIAN_RE.search(item["name"])
        for item in analysis["execution_kit"]["resources"]
    )

    chat = client.post(
        "/api/chat",
        json={
            "analysis_id": analysis["analysis_id"],
            "message": "اولین اقدام را دقیق‌تر توضیح بده",
            "locale": "en",
        },
        headers={"Accept-Language": "en"},
    )
    assert chat.status_code == 200
    chat_data = chat.json()["data"]
    assert not PERSIAN_RE.search(chat_data["message"]["content"])
    assert chat_data["execution_kit"]["additional_model_calls"] == 0

    deep = client.post(
        "/api/deep-dive",
        json={
            "analysis_id": analysis["analysis_id"],
            "step_id": analysis["action_steps"][0]["step_id"],
            "locale": "en",
        },
        headers={"Accept-Language": "en"},
    )
    assert deep.status_code == 200
    deep_data = deep.json()["data"]
    assert deep_data["lang_code"] == "en"
    assert deep_data["lang_dir"] == "ltr"
    assert not PERSIAN_RE.search(deep_data["detailed_breakdown"])
    assert deep_data["execution_kit"]["external_api_cost_usd"] == 0
    usage = client.get("/api/usage").json()["data"]
    assert usage["input_tokens"] == usage["output_tokens"] == 0


def test_multilingual_input_cannot_switch_generated_api_copy_from_english(client):
    response = client.post(
        "/api/intake",
        headers={"Accept-Language": "fa-IR,fa;q=0.9"},
        json={
            "query": "برای یک تصمیم شخصی، مسیر کم‌ریسک و قابل سنجش پیشنهاد بده",
            "tier": "B2C",
            "horizon": "instant",
            "locale": "fa",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["locale"] == "en"
    generated_copy = json.dumps(data["questions"], ensure_ascii=False)
    assert not PERSIAN_RE.search(generated_copy)
    assert client.get("/api/profile?tier=B2C").json()["data"]["locale"] == "en"


def test_english_http_errors_have_stable_code_and_no_persian(client):
    response = client.get(
        "/api/analyses/does-not-exist", headers={"Accept-Language": "en"}
    )
    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["code"] == "analysis_not_found"
    assert not PERSIAN_RE.search(detail["message"])


def test_follow_up_strategy_compaction_excludes_ui_execution_payload(app_module):
    payload = {
        "audience": "B2C",
        "signal_name": "Test",
        "executive_summary": "Summary",
        "action_steps": [
            {"step_id": "s1", "title": "Validate", "actions": ["x" * 5_000]}
        ],
        "execution_kit": {"resources": [{"raw": "x" * 50_000}]},
    }
    compact = app_module._compact_strategy_for_ai(payload)
    assert "execution_kit" not in compact
    assert "actions" not in compact["action_steps"][0]
