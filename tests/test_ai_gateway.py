from types import SimpleNamespace

import pytest

import omni_ai


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
