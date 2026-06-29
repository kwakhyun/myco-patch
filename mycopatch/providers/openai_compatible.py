from __future__ import annotations

import json
import os
import urllib.request

from mycopatch.core.cost import estimate_tokens
from mycopatch.core.models import ModelRequest, ModelResponse
from mycopatch.providers.base import BaseModelProvider, ModelProviderError


class OpenAICompatibleProvider(BaseModelProvider):
    provider_name = "openai-compatible"
    requires_network = True

    def complete(self, request: ModelRequest) -> ModelResponse:
        self._ensure_network_allowed()
        base_url = self.config.provider_base_url or "https://api.openai.com/v1/chat/completions"
        api_key = os.environ.get(self.config.api_key_env, "")
        if not api_key:
            raise ModelProviderError(
                f"Missing API key environment variable: {self.config.api_key_env}"
            )

        body = {
            "model": self.config.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are MycoPatch's advisory model layer. "
                        "Do not write source patches. Provide concise review guidance only."
                    ),
                },
                {"role": "user", "content": request.prompt},
            ],
            "max_tokens": request.max_output_tokens,
        }
        data = json.dumps(body).encode("utf-8")
        http_request = urllib.request.Request(
            base_url,
            data=data,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(http_request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))

        text = _extract_openai_text(payload)
        return ModelResponse(
            text=text,
            provider_name=self.provider_name,
            model_name=self.config.model_name,
            estimated_input_tokens=estimate_tokens(request.prompt),
            estimated_output_tokens=estimate_tokens(text),
            estimated_cost_usd=0.0,
            network_used=True,
        )


def _extract_openai_text(payload: dict) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return str(message.get("content") or "")

