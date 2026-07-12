from mycopatch.core.cost import read_cost_events
from mycopatch.core.memory import append_memory_event
from mycopatch.core.models import ModelProviderConfig, ModelRequest, ModelResponse
from mycopatch.core.patch_recommender import create_patch_recommendations
from mycopatch.core.paths import ensure_myco_layout
from mycopatch.providers.base import BaseModelProvider, ModelProviderError
from mycopatch.providers.openai_compatible import OpenAICompatibleProvider
from mycopatch.providers.service import invoke_model_provider


class FakeModelProvider(BaseModelProvider):
    provider_name = "fake"
    requires_network = False

    def complete(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            text=f"fake response for {request.task}",
            provider_name=self.provider_name,
            model_name="fake-model",
            estimated_input_tokens=3,
            estimated_output_tokens=4,
            estimated_cost_usd=0.0,
        )


class FakeNetworkProvider(FakeModelProvider):
    requires_network = True

    def __init__(self, config):
        super().__init__(config)
        self.called = False

    def complete(self, request):
        self.called = True
        return super().complete(request)


def test_fake_model_provider_call_is_recorded_in_cost_ledger(tmp_path):
    ensure_myco_layout(tmp_path)
    provider = FakeModelProvider(ModelProviderConfig(model_name="fake-model"))

    response = invoke_model_provider(
        tmp_path,
        task="suggest_probe_ideas",
        prompt="datetime.utcnow risk with no nearby test",
        provider=provider,
    )

    events = read_cost_events(tmp_path)
    assert response.provider_name == "fake"
    assert events[-1].event_type == "model_call_recorded"
    assert events[-1].task == "suggest_probe_ideas"
    assert events[-1].provider_name == "fake"
    assert events[-1].model_name == "fake-model"


def test_network_provider_without_explicit_permission_falls_back_offline(tmp_path):
    paths = ensure_myco_layout(tmp_path)
    paths.config.write_text(
        """
default_provider = "openai-compatible"
model_name = "gpt-test"
max_input_tokens = 100
max_output_tokens = 50
max_cost_usd = 0.0
allow_network_for_model_provider = false
provider_base_url = "https://example.invalid/v1/chat/completions"
api_key_env = "MYCO_TEST_KEY"
""",
        encoding="utf-8",
    )

    response = invoke_model_provider(
        tmp_path,
        task="summarize_failure_logs",
        prompt="FAILED aggressive probe assertion",
    )

    assert response.provider_name == "offline"
    assert not response.network_used
    assert "Model provider skipped" in response.text
    assert read_cost_events(tmp_path)[-1].event_type == "model_call_recorded"


def test_zero_cost_budget_blocks_network_provider_before_call(tmp_path):
    ensure_myco_layout(tmp_path)
    config = ModelProviderConfig(
        default_provider="openai-compatible",
        model_name="fake-network",
        allow_network_for_model_provider=True,
        max_cost_usd=0.0,
    )
    provider = FakeNetworkProvider(config)

    response = invoke_model_provider(
        tmp_path,
        task="suggest_probe_ideas",
        prompt="risk",
        provider=provider,
        config=config,
    )

    assert not provider.called
    assert response.provider_name == "offline"
    assert "max_cost_usd" in response.text
    assert read_cost_events(tmp_path)[-1].event_type == "model_call_recorded"


def test_openai_compatible_provider_wraps_network_errors(monkeypatch):
    config = ModelProviderConfig(
        default_provider="openai-compatible",
        model_name="test-model",
        allow_network_for_model_provider=True,
        max_cost_usd=1.0,
        api_key_env="MYCO_TEST_KEY",
    )
    provider = OpenAICompatibleProvider(config)
    request = ModelRequest(
        task="suggest_probe_ideas",
        prompt="risk",
        max_input_tokens=100,
        max_output_tokens=20,
    )
    monkeypatch.setenv("MYCO_TEST_KEY", "secret")
    monkeypatch.setattr(
        "mycopatch.providers.openai_compatible.urllib.request.urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(urllib.error.URLError("offline")),
    )

    with pytest.raises(ModelProviderError, match="request failed"):
        provider.complete(request)


def test_patch_recommender_uses_fake_provider_for_advisory_text(tmp_path):
    ensure_myco_layout(tmp_path)
    provider = FakeModelProvider(ModelProviderConfig(model_name="fake-model"))
    append_memory_event(
        tmp_path,
        "probe_failed",
        {
            "probe": {
                "target_file": "billing.py",
                "path": ".myco/probes/generated_tests/test_probe.py",
                "evidence": ["L3: return datetime.utcnow()"],
            },
            "result": {
                "probe_path": ".myco/probes/generated_tests/test_probe.py",
                "stdout": "FAILED aggressive probe assertion",
                "stderr": "",
            },
        },
    )

    recommendations = create_patch_recommendations(tmp_path, provider=provider)

    assert len(recommendations) == 1
    assert recommendations[0].provider_name == "fake"
    assert recommendations[0].failure_summary == "fake response for summarize_failure_logs"
    assert recommendations[0].suggested_manual_fix_strategy == "fake response for draft_patch_recommendation"
    model_events = [
        event for event in read_cost_events(tmp_path) if event.event_type == "model_call_recorded"
    ]
    assert [event.task for event in model_events] == [
        "summarize_failure_logs",
        "draft_patch_recommendation",
    ]
import urllib.error

import pytest
