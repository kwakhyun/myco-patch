from __future__ import annotations

from abc import ABC, abstractmethod

from mycopatch.core.models import ModelProviderConfig, ModelRequest, ModelResponse


class ModelProviderError(RuntimeError):
    """Raised when a model provider cannot complete a request."""


class NetworkModelProviderDisabled(ModelProviderError):
    """Raised when a network provider is requested without explicit permission."""


class ModelBudgetExceeded(ModelProviderError):
    """Raised before a network call when no external model cost is authorized."""


class BaseModelProvider(ABC):
    provider_name = "base"
    requires_network = False

    def __init__(self, config: ModelProviderConfig) -> None:
        self.config = config

    @abstractmethod
    def complete(self, request: ModelRequest) -> ModelResponse:
        """Return model text for an allowed advisory task."""

    def _ensure_network_allowed(self) -> None:
        if self.requires_network and not self.config.allow_network_for_model_provider:
            raise NetworkModelProviderDisabled(
                f"Provider '{self.provider_name}' requires network access. "
                "Set allow_network_for_model_provider = true in .myco/config.toml to enable it."
            )
