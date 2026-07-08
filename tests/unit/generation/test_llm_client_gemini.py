"""Unit tests for GeminiProvider's thinking-budget / JSON-mode config.

Regression test for a bug where gemini-2.5-flash's default "thinking" mode
silently consumed the entire ``max_output_tokens`` budget before writing any
answer, producing an empty/truncated response that failed the output
guardrail on every single request (see ``src/guardrails/output/validator.py``
and ``GUARDRAIL_PLAN.md``). The fix disables thinking for flash/flash-lite
models (which support ``thinking_budget=0``) while leaving pro models
untouched (they do not support disabling thinking).
"""

from unittest.mock import MagicMock

from src.generation.llm_client import GeminiProvider


def _provider_with_fake_client(model: str, response_text: str) -> tuple[GeminiProvider, MagicMock]:
    provider = GeminiProvider(model=model)
    fake_client = MagicMock()
    fake_response = MagicMock()
    fake_response.text = response_text
    fake_client.models.generate_content.return_value = fake_response
    provider.client = fake_client
    return provider, fake_client


def test_flash_json_output_disables_thinking_and_sets_json_mime_type():
    provider, fake_client = _provider_with_fake_client(
        "gemini-2.5-flash", '{"recommendations": [], "summary": ""}'
    )

    result = provider.generate("prompt", system_prompt="sys", json_output=True)

    assert result == '{"recommendations": [], "summary": ""}'
    _, kwargs = fake_client.models.generate_content.call_args
    config = kwargs["config"]
    assert config.response_mime_type == "application/json"
    assert config.thinking_config is not None
    assert config.thinking_config.thinking_budget == 0


def test_flash_non_json_call_still_disables_thinking():
    provider, fake_client = _provider_with_fake_client("gemini-2.5-flash", "plain text")

    provider.generate("prompt")

    _, kwargs = fake_client.models.generate_content.call_args
    config = kwargs["config"]
    assert config.response_mime_type is None
    assert config.thinking_config is not None
    assert config.thinking_config.thinking_budget == 0


def test_pro_model_leaves_thinking_config_untouched():
    provider, fake_client = _provider_with_fake_client("gemini-2.5-pro", '{"a": 1}')

    provider.generate("prompt", json_output=True)

    _, kwargs = fake_client.models.generate_content.call_args
    config = kwargs["config"]
    # gemini-2.5-pro does not support thinking_budget=0, so it must be left
    # at the SDK default (None) rather than forcibly disabled.
    assert config.thinking_config is None
    assert config.response_mime_type == "application/json"


def test_flash_lite_also_disables_thinking():
    provider, fake_client = _provider_with_fake_client("gemini-2.5-flash-lite", "{}")

    provider.generate("prompt", json_output=True)

    _, kwargs = fake_client.models.generate_content.call_args
    config = kwargs["config"]
    assert config.thinking_config is not None
    assert config.thinking_config.thinking_budget == 0
