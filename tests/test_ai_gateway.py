from types import SimpleNamespace

import pytest

import omni_ai


def _mocked_provider_gateway(parsed, *, model="gpt-4o-mini"):
    captured = {}

    class FakeResponses:
        async def parse(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                id="resp_english_output_test",
                status="completed",
                model=model,
                output_parsed=parsed,
                usage=SimpleNamespace(
                    input_tokens=21,
                    output_tokens=34,
                    total_tokens=55,
                    input_tokens_details=None,
                    output_tokens_details=None,
                ),
            )

    class FakeClient:
        responses = FakeResponses()

        async def close(self):
            return None

    gateway = omni_ai.OmniAIGateway(
        settings=omni_ai.GatewaySettings(demo_mode=False)
    )
    gateway._client = FakeClient()
    return gateway, captured


def _assert_english_only_violation(exc_info, expected_path, rejected_text):
    error = exc_info.value
    assert error.code == "ai_response_validation_failed"
    assert error.response_id == "resp_english_output_test"
    assert error.usage.total_tokens == 55
    assert "English-only output requirement" in str(error)
    assert expected_path in str(error.cause)
    assert rejected_text not in str(error)
    assert rejected_text not in str(error.cause)


@pytest.mark.asyncio
async def test_demo_gateway_is_lazy_and_uses_zero_tokens(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    gateway = omni_ai.OmniAIGateway(demo_mode=True)
    assert gateway.client_initialized is False
    result = await gateway.analyze(
        query="من برای یک تصمیم شخصی به برنامه دقیق نیاز دارم",
        tier="B2C",
        horizon="instant",
    )
    assert result.demo_mode is True
    assert result.usage.total_tokens == 0
    assert gateway.client_initialized is False
    assert result.data.lang_code == "en"
    assert result.data.lang_dir == "ltr"
    assert not any(
        "\u0600" <= character <= "\u06ff"
        for character in result.data.executive_summary
    )


@pytest.mark.asyncio
async def test_real_request_contract_is_bounded_private_and_cache_friendly():
    captured = {}
    parsed = omni_ai._demo_analysis("B2C", "instant", "یک درخواست معتبر برای تست")

    class FakeResponses:
        async def parse(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                id="resp_contract_test",
                status="completed",
                model="gpt-5-mini",
                output_parsed=parsed,
                usage=SimpleNamespace(
                    input_tokens=21,
                    output_tokens=34,
                    total_tokens=55,
                    input_tokens_details=None,
                    output_tokens_details=None,
                ),
            )

    class FakeClient:
        responses = FakeResponses()

        async def close(self):
            return None

    settings = omni_ai.GatewaySettings(demo_mode=False, reasoning_effort="low")
    gateway = omni_ai.OmniAIGateway(settings=settings)
    gateway._client = FakeClient()
    result = await gateway.analyze(
        query="من برای یک تصمیم شخصی به برنامه دقیق نیاز دارم",
        tier="B2C",
        horizon="instant",
    )

    assert result.usage.total_tokens == 55
    assert captured["store"] is False
    assert captured["truncation"] == "disabled"
    assert captured["max_output_tokens"] == settings.analysis_max_output_tokens
    assert captured["prompt_cache_key"] == "omni-analysis-v2"
    assert captured["reasoning"] == {"effort": "low"}
    assert captured["text_format"] is omni_ai.B2CAnalysis


@pytest.mark.asyncio
async def test_live_analysis_accepts_multilingual_input_and_opaque_identifiers():
    parsed = omni_ai._demo_analysis("B2C", "instant", "English fixture")
    payload = parsed.model_dump(mode="python")
    payload["action_steps"][0]["step_id"] = "\u06af\u0627\u0645_1"
    parsed = omni_ai.B2CAnalysis.model_validate(payload, strict=True)
    gateway, captured = _mocked_provider_gateway(parsed, model="gpt-5-mini")

    result = await gateway.analyze(
        query="\u0645\u0646 \u0628\u0647 \u06cc\u06a9 \u0628\u0631\u0646\u0627\u0645\u0647 \u0627\u06cc\u0645\u0646 \u0646\u06cc\u0627\u0632 \u062f\u0627\u0631\u0645",
        tier="B2C",
        horizon="instant",
    )

    assert (
        "\u0645\u0646 \u0628\u0647 \u06cc\u06a9 \u0628\u0631\u0646\u0627\u0645\u0647"
        in captured["input"][0]["content"]
    )
    assert result.data.action_steps[0].step_id == "\u06af\u0627\u0645_1"


@pytest.mark.asyncio
async def test_live_analysis_rejects_arabic_script_in_displayed_source_label():
    parsed = omni_ai._demo_analysis("B2C", "instant", "English fixture")
    first_evidence = parsed.evidence[0].model_copy(
        update={"source_key": "\u0645\u0646\u0628\u0639"}
    )
    parsed = parsed.model_copy(
        update={"evidence": [first_evidence, *parsed.evidence[1:]]}
    )
    gateway, _ = _mocked_provider_gateway(parsed, model="gpt-5-mini")

    with pytest.raises(omni_ai.AIResponseValidationError) as exc_info:
        await gateway.analyze(query="English request", tier="B2C", horizon="instant")

    _assert_english_only_violation(
        exc_info,
        "evidence[0].source_key",
        "\u0645\u0646\u0628\u0639",
    )


@pytest.mark.asyncio
async def test_live_chat_rejects_arabic_script_in_list_prose():
    parsed = omni_ai._demo_chat("English follow-up").model_copy(
        update={"key_points": ["Arabic supplement: \u0750"]}
    )
    gateway, _ = _mocked_provider_gateway(parsed)

    with pytest.raises(omni_ai.AIResponseValidationError) as exc_info:
        await gateway.chat(
            user_message="English follow-up",
            tier="B2C",
            horizon="instant",
            strategy={},
        )

    _assert_english_only_violation(exc_info, "key_points[0]", "\u0750")


@pytest.mark.asyncio
async def test_live_deep_dive_rejects_arabic_script_in_nested_prose():
    parsed = omni_ai._demo_deep_dive("English question")
    first_sub_step = parsed.sub_steps[0].model_copy(
        update={"rationale": "Presentation form: \ufb8e"}
    )
    parsed = parsed.model_copy(
        update={"sub_steps": [first_sub_step, *parsed.sub_steps[1:]]}
    )
    gateway, _ = _mocked_provider_gateway(parsed)

    with pytest.raises(omni_ai.AIResponseValidationError) as exc_info:
        await gateway.deep_dive(
            step="step_1",
            tier="B2C",
            horizon="instant",
            strategy_summary={},
        )

    _assert_english_only_violation(exc_info, "sub_steps[0].rationale", "\ufb8e")
