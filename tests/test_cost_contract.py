from __future__ import annotations

import pytest
from pydantic import ValidationError

import omni_ai


def test_environment_cannot_raise_models_tokens_or_reasoning_cost(monkeypatch):
    expensive_overrides = {
        "OMNI_OPENAI_ANALYSIS_MODEL": "gpt-5-pro",
        "OMNI_OPENAI_CHAT_MODEL": "gpt-5",
        "OMNI_OPENAI_DEEP_DIVE_MODEL": "gpt-5-pro",
        "OMNI_AI_ANALYSIS_MAX_OUTPUT_TOKENS": "999999",
        "OMNI_AI_CHAT_MAX_OUTPUT_TOKENS": "999999",
        "OMNI_AI_DEEP_DIVE_MAX_OUTPUT_TOKENS": "999999",
        "OMNI_AI_REASONING_EFFORT": "high",
        # Aliases must not bypass the canonical cost lock either.
        "OMNI_ANALYSIS_MODEL": "gpt-5-pro",
        "OMNI_CHAT_MODEL": "gpt-5-pro",
        "OMNI_DEEP_DIVE_MODEL": "gpt-5-pro",
        "OMNI_ANALYSIS_MAX_OUTPUT_TOKENS": "999999",
        "OMNI_CHAT_MAX_OUTPUT_TOKENS": "999999",
        "OMNI_DEEP_DIVE_MAX_OUTPUT_TOKENS": "999999",
        "OMNI_REASONING_EFFORT": "high",
        "OMNI_AI_MAX_QUERY_CHARS": "999999",
        "OMNI_AI_MAX_CONTEXT_CHARS": "999999",
        "OMNI_AI_MAX_HISTORY_MESSAGES": "999999",
    }
    for name, value in expensive_overrides.items():
        monkeypatch.setenv(name, value)

    settings = omni_ai.GatewaySettings.from_env()
    assert settings.analysis_model == "gpt-5-mini"
    assert settings.chat_model == "gpt-4o-mini"
    assert settings.deep_dive_model == "gpt-4o-mini"
    assert settings.analysis_max_output_tokens == 2_600
    assert settings.chat_max_output_tokens == 700
    assert settings.deep_dive_max_output_tokens == 1_000
    assert settings.reasoning_effort == "low"
    assert settings.max_query_chars == 8_000
    assert settings.max_context_chars == 50_000
    assert settings.max_history_messages == 12


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("analysis_max_output_tokens", 2_601),
        ("chat_max_output_tokens", 701),
        ("deep_dive_max_output_tokens", 1_001),
    ],
)
def test_gateway_schema_rejects_values_above_product_hard_caps(field, value):
    with pytest.raises(ValidationError):
        omni_ai.GatewaySettings(**{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_query_chars", 8_001),
        ("max_context_chars", 50_001),
        ("max_history_messages", 13),
    ],
)
def test_gateway_schema_rejects_input_context_above_cost_caps(field, value):
    with pytest.raises(ValidationError):
        omni_ai.GatewaySettings(**{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("analysis_model", "gpt-5-pro"),
        ("chat_model", "gpt-5"),
        ("deep_dive_model", "gpt-5-pro"),
        ("reasoning_effort", "high"),
    ],
)
def test_direct_settings_cannot_bypass_model_or_reasoning_cost_lock(field, value):
    with pytest.raises(ValidationError):
        omni_ai.GatewaySettings(**{field: value})


def test_lower_output_budgets_are_allowed_but_reasoning_remains_low(monkeypatch):
    monkeypatch.setenv("OMNI_AI_ANALYSIS_MAX_OUTPUT_TOKENS", "512")
    monkeypatch.setenv("OMNI_AI_CHAT_MAX_OUTPUT_TOKENS", "128")
    monkeypatch.setenv("OMNI_AI_DEEP_DIVE_MAX_OUTPUT_TOKENS", "256")
    monkeypatch.setenv("OMNI_AI_REASONING_EFFORT", "high")

    settings = omni_ai.GatewaySettings.from_env()
    assert settings.analysis_max_output_tokens == 512
    assert settings.chat_max_output_tokens == 128
    assert settings.deep_dive_max_output_tokens == 256
    assert settings.reasoning_effort == "low"


def test_prompts_require_free_methods_and_forbid_invented_destinations():
    assert "Prefer free, keyless, or free-account" in omni_ai.ANALYSIS_SYSTEM_INSTRUCTIONS
    for instructions in (
        omni_ai.ANALYSIS_SYSTEM_INSTRUCTIONS,
        omni_ai.CHAT_SYSTEM_INSTRUCTIONS,
        omni_ai.DEEP_DIVE_SYSTEM_INSTRUCTIONS,
    ):
        assert "invent urls" in instructions.lower()
