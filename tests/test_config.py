import pytest

from claim_assessor.config import Settings


def test_settings_reads_provider_env_and_hides_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_MODEL", "test-model")
    monkeypatch.setenv("GEMINI_API_KEY", "secret-value")

    settings = Settings(_env_file=None)

    assert settings.gemini_model == "test-model"
    assert "secret-value" not in repr(settings)
