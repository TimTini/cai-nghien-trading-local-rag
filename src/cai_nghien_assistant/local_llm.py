"""Optional local llama.cpp HTTP adapter."""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class LlamaCppClient:
    endpoint: str
    timeout: int = 120

    def complete(self, prompt: str, max_tokens: int = 900, temperature: float = 0.1) -> str:
        payload = {
            "prompt": prompt,
            "n_predict": max_tokens,
            "temperature": temperature,
            "cache_prompt": True,
        }
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:  # nosec - local user endpoint
            data = json.loads(response.read().decode("utf-8"))
        return str(data.get("content") or data.get("response") or data.get("text") or "")

