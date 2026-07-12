from __future__ import annotations

from pathlib import Path

from mycopatch.core.config import load_config
from mycopatch.core.cost import record_cost_event
from mycopatch.core.models import (
    ModelProviderConfig,
    ModelRequest,
    ModelResponse,
)
from mycopatch.providers.base import (
    BaseModelProvider,
    ModelBudgetExceeded,
    ModelProviderError,
    NetworkModelProviderDisabled,
)
from mycopatch.providers.local_http import LocalHTTPProvider
from mycopatch.providers.offline import OfflineHeuristicProvider
from mycopatch.providers.openai_compatible import OpenAICompatibleProvider


def get_model_provider(config: ModelProviderConfig) -> BaseModelProvider:
    providers = {
        "offline": OfflineHeuristicProvider,
        "openai-compatible": OpenAICompatibleProvider,
        "local-http": LocalHTTPProvider,
    }
    return providers[config.default_provider](config)


def invoke_model_provider(
    repo_root: Path | str,
    *,
    task: str,
    prompt: str,
    provider: BaseModelProvider | None = None,
    config: ModelProviderConfig | None = None,
) -> ModelResponse:
    active_config = config or load_config(repo_root)
    request = ModelRequest(
        task=task,
        prompt=_truncate_prompt(prompt, active_config.max_input_tokens),
        max_input_tokens=active_config.max_input_tokens,
        max_output_tokens=active_config.max_output_tokens,
    )
    active_provider = provider or get_model_provider(active_config)
    try:
        if active_provider.requires_network and active_config.max_cost_usd <= 0:
            raise ModelBudgetExceeded(
                "Network model calls require max_cost_usd to be greater than zero."
            )
        response = active_provider.complete(request)
    except NetworkModelProviderDisabled as exc:
        response = _offline_fallback_response(active_config, request, str(exc))
    except ModelProviderError as exc:
        response = _offline_fallback_response(active_config, request, str(exc))

    if response.estimated_cost_usd > active_config.max_cost_usd:
        response.text = (
            "Model response exceeded the configured max_cost_usd budget and was not used."
        )
        response.estimated_cost_usd = 0.0

    record_cost_event(
        repo_root,
        event_type="model_call_recorded",
        task=task,
        provider_name=response.provider_name,
        model_name=response.model_name,
        input_text=request.prompt,
        output_text=response.text,
        estimated_cost_usd=response.estimated_cost_usd,
        budget_limit=active_config.max_input_tokens,
        notes=f"model provider advisory call: {task}",
    )
    return response


def _offline_fallback_response(
    active_config: ModelProviderConfig,
    request: ModelRequest,
    reason: str,
) -> ModelResponse:
    fallback_config = active_config.model_copy(
        update={
            "default_provider": "offline",
            "model_name": "offline-heuristic",
            "allow_network_for_model_provider": False,
        }
    )
    fallback = OfflineHeuristicProvider(fallback_config)
    response = fallback.complete(request)
    response.text = f"{response.text}\n\nModel provider skipped: {reason}"
    return response


def _truncate_prompt(prompt: str, max_input_tokens: int) -> str:
    max_chars = max_input_tokens * 4
    if len(prompt) <= max_chars:
        return prompt
    return prompt[:max_chars] + "\n[truncated by MycoPatch token budget]"
