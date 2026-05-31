"""Minimal OpenRouter chat client (no SDK)."""
from __future__ import annotations
import json
import os
import random
import time
from typing import Any

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Map of short-name → OpenRouter slug. Verify on https://openrouter.ai/models
# before each run; OpenRouter renames slugs occasionally.
DEFAULT_MODELS: dict[str, str] = {
    "claude_4_7": "anthropic/claude-opus-4.7",
    "gpt_5_5":    "openai/gpt-5.5",
    "gemini_3_1": "google/gemini-3.1-pro-preview",
}


class OpenRouterClient:
    def __init__(
        self,
        api_key: str | None = None,
        referer: str = "https://github.com/yilin/robostance",
        title: str = "RoboStance-stance-annotation",
        timeout: int = 60,
    ):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY not set. Put it in phase1/llm_stance/.env "
                "or export it before running."
            )
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": referer,   # OpenRouter recommended
            "X-Title": title,
        }
        self.timeout = timeout

    def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.0,
        max_tokens: int = 256,
        max_retries: int = 4,
    ) -> dict[str, Any]:
        """Call /chat/completions with exponential backoff on retryable errors.

        Returns the parsed JSON response dict; raises RuntimeError on terminal
        failure.
        """
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        last_err: str | None = None
        for attempt in range(max_retries):
            try:
                r = requests.post(
                    OPENROUTER_URL,
                    headers=self.headers,
                    data=json.dumps(payload),
                    timeout=self.timeout,
                )
                if r.status_code == 200:
                    return r.json()
                # 429 / 5xx → retry; 4xx other → fail fast
                if r.status_code in (408, 409, 425, 429) or r.status_code >= 500:
                    last_err = f"HTTP {r.status_code}: {r.text[:300]}"
                else:
                    raise RuntimeError(
                        f"OpenRouter HTTP {r.status_code}: {r.text[:300]}"
                    )
            except requests.RequestException as e:
                last_err = f"requests error: {e!r}"
            # back-off
            sleep_s = (2 ** attempt) + random.random()
            time.sleep(sleep_s)
        raise RuntimeError(f"OpenRouter failed after {max_retries} attempts: {last_err}")

    @staticmethod
    def extract_text(resp: dict[str, Any]) -> str:
        """Pull assistant message content from an OpenRouter chat response."""
        try:
            return resp["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError(f"Unexpected OpenRouter response shape: {resp}") from e
