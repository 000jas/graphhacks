from __future__ import annotations

import pytest

from agent.config import AgentSettings, mask_secret


def test_mask_secret() -> None:
    assert mask_secret(None) == "<not set>"
    assert mask_secret("") == "<not set>"
    assert mask_secret("short") == "****"
    assert mask_secret("nvapi-1234567890abcdef") == "nvap...cdef"


def test_provider_configuration_validation() -> None:
    s_nvidia = AgentSettings(llm_provider="nvidia", nvidia_api_key=None)
    with pytest.raises(ValueError, match="NVIDIA_API_KEY is not set"):
        s_nvidia.validate_provider_configuration()

    s_nvidia_valid = AgentSettings(
        llm_provider="nvidia",
        nvidia_api_key="nvapi-test123456",
        llm_api_base="https://integrate.api.nvidia.com/v1",
    )
    s_nvidia_valid.validate_provider_configuration()

    s_openai = AgentSettings(llm_provider="openai", openai_api_key=None)
    with pytest.raises(ValueError, match="OPENAI_API_KEY is not set"):
        s_openai.validate_provider_configuration()

    s_anthropic = AgentSettings(llm_provider="anthropic", anthropic_api_key=None)
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY is not set"):
        s_anthropic.validate_provider_configuration()

    s_invalid = AgentSettings(llm_provider="unsupported_vendor")
    with pytest.raises(ValueError, match="Unsupported LLM_PROVIDER"):
        s_invalid.validate_provider_configuration()

    s_mock = AgentSettings(llm_provider="mock")
    s_mock.validate_provider_configuration()


def test_masked_diagnostics_never_exposes_secrets() -> None:
    raw_key = "nvapi-SUPER_SECRET_KEY_123456789"
    s = AgentSettings(
        llm_provider="nvidia",
        nvidia_api_key=raw_key,
        llm_model="openai/gpt-oss-20b",
    )
    diag = s.masked_diagnostics()
    assert diag["active_provider"] == "nvidia"
    assert diag["active_model"] == "openai/gpt-oss-20b"
    assert raw_key not in str(diag)
    assert diag["credential_masked"].startswith("nvap...")
