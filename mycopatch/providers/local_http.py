from __future__ import annotations

import json
import urllib.request

from mycopatch.core.cost import estimate_tokens
from mycopatch.core.models import ModelRequest, ModelResponse
from mycopatch.providers.base import BaseModelProvider, ModelProviderError


class LocalHTTPProvider(BaseModelProvider):
    provider_name = "local-http"
    requires_network = True

    def complete(self, request: ModelRequest) -> ModelResponse:
        self._ensure_network_allowed()
        if not self.config.provider_base_url:
            raise ModelProviderError(
                "LocalHTTPProvider requires provider_base_url in .myco/config.toml."
            )

        body = {
            "model": self.config.model_name,
            "task": request.task,
            "prompt": request.prompt,
            "max_input_tokens": request.max_input_tokens,
            "max_output_tokens": request.max_output_tokens,
        }
        data = json.dumps(body).encode("utf-8")
        http_request = urllib.request.Request(
            self.config.provider_base_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(http_request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))

        text = str(payload.get("text") or payload.get("content") or "")
        return ModelResponse(
            text=text,
            provider_name=self.provider_name,
            model_name=self.config.model_name,
            estimated_input_tokens=estimate_tokens(request.prompt),
            estimated_output_tokens=estimate_tokens(text),
            estimated_cost_usd=0.0,
            network_used=True,
        )

