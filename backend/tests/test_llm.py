"""LLM provider-chain tests (offline, no real API calls)."""

from types import SimpleNamespace

from app.services import llm as llm_module


def test_provider_chain_includes_fallback(monkeypatch):
    monkeypatch.setattr(llm_module.settings, "llm_api_key", "primary-key")
    monkeypatch.setattr(llm_module.settings, "groq_api_key", "fallback-key")
    monkeypatch.setattr(llm_module.settings, "llm_fallback_api_key", "")
    providers = llm_module.llm_client._providers()
    assert [p["name"] for p in providers] == ["openrouter", "groq"]
    assert providers[1]["base_url"] == "https://api.groq.com/openai/v1"


async def test_acomplete_falls_back_when_primary_fails(monkeypatch):
    monkeypatch.setattr(llm_module.settings, "llm_api_key", "primary-key")
    monkeypatch.setattr(llm_module.settings, "groq_api_key", "fallback-key")
    monkeypatch.setattr(llm_module.settings, "llm_fallback_api_key", "")

    class FakeCompletions:
        def __init__(self, fail: bool) -> None:
            self.fail = fail

        async def create(self, **kwargs):
            if self.fail:
                raise RuntimeError("primary exhausted credits")
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="FALLBACK_OK"))]
            )

    fake_clients = {
        "openrouter": SimpleNamespace(
            chat=SimpleNamespace(completions=FakeCompletions(True))
        ),
        "groq": SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions(False))),
    }

    async def fake_client_for(provider):
        return fake_clients[provider["name"]]

    monkeypatch.setattr(llm_module.llm_client, "_client_for", fake_client_for)
    result = await llm_module.llm_client.acomplete(
        [{"role": "user", "content": "hello"}]
    )
    assert result == "FALLBACK_OK"


async def test_acomplete_without_any_key_raises(monkeypatch):
    monkeypatch.setattr(llm_module.settings, "llm_api_key", "")
    monkeypatch.setattr(llm_module.settings, "groq_api_key", "")
    monkeypatch.setattr(llm_module.settings, "llm_fallback_api_key", "")
    try:
        await llm_module.llm_client.acomplete([{"role": "user", "content": "hi"}])
    except llm_module.LLMUnavailableError:
        return
    raise AssertionError("Expected LLMUnavailableError")
