"""OpenAI-compatible chat clients: OpenRouter, SiliconFlow, DeepSeek."""
from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass, field
from typing import Any

import requests

# Pattern from relic_3/scripts/pipeline/run_inference.py


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    base_url: str
    api_key_env: tuple[str, ...]
    extra_headers: dict[str, str] = field(default_factory=dict)


PROVIDER_CONFIGS: dict[str, ProviderConfig] = {
    "openrouter": ProviderConfig(
        name="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key_env=("OPENROUTER_API_KEY",),
        extra_headers={
            "HTTP-Referer": "https://github.com/yilin/robostance",
            "X-Title": "Human-LLM-eval",
        },
    ),
    "siliconflow": ProviderConfig(
        name="siliconflow",
        base_url="https://api.siliconflow.cn/v1",
        api_key_env=("SILICONFLOW_API_KEY", "SILICONFLOW_api_key", "SILICONFLOW_API_key"),
    ),
    "deepseek": ProviderConfig(
        name="deepseek",
        base_url="https://api.deepseek.com",
        api_key_env=("DEEPSEEK_API_KEY",),
    ),
}

FATAL_STATUS = {401, 403}


@dataclass
class ModelSpec:
    key: str
    chain: list[tuple[str, str]]
    reasoning_mode: str = "off"  # off | on
    reasoning_effort: str = "high"  # deepseek/openrouter: high/max; siliconflow uses budget
    reasoning_max_tokens: int | None = None  # openrouter / siliconflow thinking budget


def get_env_api_key(env_names: tuple[str, ...]) -> str:
    for name in env_names:
        val = (os.environ.get(name) or "").strip()
        if val:
            return val
    return ""


def _normalize_reasoning_mode(raw: Any) -> str:
    s = str(raw or "off").strip().lower()
    if s in ("on", "true", "yes", "enabled", "1"):
        return "on"
    return "off"


def build_reasoning_extras(
    provider: str,
    *,
    reasoning_mode: str,
    reasoning_effort: str = "high",
    reasoning_max_tokens: int | None = None,
) -> dict[str, Any]:
    """Provider-specific reasoning params merged into chat payload."""
    on = reasoning_mode == "on"
    extras: dict[str, Any] = {}

    if provider == "deepseek":
        extras["thinking"] = {"type": "enabled" if on else "disabled"}
        if on:
            effort = reasoning_effort if reasoning_effort in ("high", "max") else "high"
            extras["reasoning_effort"] = effort
        return extras

    if provider == "siliconflow":
        if on:
            budget = reasoning_max_tokens if reasoning_max_tokens is not None else 8192
            extras["enable_thinking"] = True
            extras["thinking_budget"] = budget
        else:
            extras["enable_thinking"] = False
        return extras

    if provider == "openrouter":
        if on:
            if reasoning_max_tokens is not None:
                extras["reasoning"] = {"max_tokens": reasoning_max_tokens, "exclude": False}
            else:
                effort = reasoning_effort if reasoning_effort in ("minimal", "low", "medium", "high", "xhigh") else "xhigh"
                extras["reasoning"] = {"effort": effort, "exclude": False}
        else:
            extras["reasoning"] = {"effort": "none", "exclude": False}
        return extras

    return extras


class ChatClient:
    """Sync OpenAI-compatible /chat/completions client for one provider."""

    def __init__(
        self,
        provider: ProviderConfig,
        *,
        api_key: str | None = None,
        timeout: int = 120,
    ):
        self.provider = provider
        self.api_key = api_key or get_env_api_key(provider.api_key_env)
        if not self.api_key:
            raise RuntimeError(
                f"{provider.name}: set one of {provider.api_key_env} in .env or environment"
            )
        self.timeout = timeout
        self.base_url = provider.base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **provider.extra_headers,
        }

    def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.0,
        max_tokens: int = 512,
        reasoning_mode: str = "off",
        reasoning_effort: str = "high",
        reasoning_max_tokens: int | None = None,
        max_retries: int = 4,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        payload.update(
            build_reasoning_extras(
                self.provider.name,
                reasoning_mode=reasoning_mode,
                reasoning_effort=reasoning_effort,
                reasoning_max_tokens=reasoning_max_tokens,
            )
        )
        last_err: str | None = None
        for attempt in range(max_retries):
            try:
                r = requests.post(
                    url,
                    headers=self.headers,
                    data=json.dumps(payload),
                    timeout=self.timeout,
                )
                if r.status_code == 200:
                    return r.json()
                if r.status_code in FATAL_STATUS:
                    raise RuntimeError(
                        f"{self.provider.name} HTTP {r.status_code}: {r.text[:300]}"
                    )
                if r.status_code in (408, 409, 425, 429) or r.status_code >= 500:
                    last_err = f"HTTP {r.status_code}: {r.text[:300]}"
                else:
                    raise RuntimeError(
                        f"{self.provider.name} HTTP {r.status_code}: {r.text[:300]}"
                    )
            except requests.RequestException as e:
                last_err = f"requests error: {e!r}"
            time.sleep((2**attempt) + random.random())
        raise RuntimeError(
            f"{self.provider.name} failed after {max_retries} attempts: {last_err}"
        )

    @staticmethod
    def extract_message(resp: dict[str, Any]) -> tuple[str, str]:
        """Return (content, reasoning_content) from assistant message."""
        try:
            msg = resp["choices"][0]["message"]
            content = str(msg.get("content") or "")
            reasoning = str(msg.get("reasoning_content") or msg.get("reasoning") or "")
            return content, reasoning
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError(f"Unexpected chat response shape: {resp}") from e

    @staticmethod
    def extract_text(resp: dict[str, Any]) -> str:
        content, _ = ChatClient.extract_message(resp)
        return content

    @staticmethod
    def assistant_message_from_response(resp: dict[str, Any]) -> dict[str, str]:
        """Build assistant message for multi-turn; preserves DeepSeek reasoning_content."""
        content, reasoning = ChatClient.extract_message(resp)
        msg: dict[str, str] = {"role": "assistant", "content": content}
        if reasoning.strip():
            msg["reasoning_content"] = reasoning
        return msg


@dataclass
class ProviderEngine:
    provider: str
    model: str
    client: ChatClient


class ProviderChain:
    """Try providers in order; same pattern as relic_3 ProviderChain."""

    def __init__(
        self,
        spec: ModelSpec,
        *,
        timeout: int = 120,
    ):
        self.spec = spec
        self.model_key = spec.key
        self.reasoning_mode = spec.reasoning_mode
        self.reasoning_effort = spec.reasoning_effort
        self.reasoning_max_tokens = spec.reasoning_max_tokens
        self.engines: list[ProviderEngine] = []
        for provider_name, model_slug in spec.chain:
            cfg = PROVIDER_CONFIGS.get(provider_name)
            if cfg is None:
                continue
            if not get_env_api_key(cfg.api_key_env):
                continue
            self.engines.append(
                ProviderEngine(
                    provider=provider_name,
                    model=model_slug,
                    client=ChatClient(cfg, timeout=timeout),
                )
            )
        if not self.engines:
            raise RuntimeError(
                f"model {spec.key!r}: no provider available "
                f"(chain={spec.chain!r}, check API keys)"
            )

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> tuple[dict[str, Any], str, str]:
        """Returns (response_dict, provider_used, model_used)."""
        last_err: Exception | None = None
        for eng in self.engines:
            try:
                resp = eng.client.chat(
                    eng.model,
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    reasoning_mode=self.reasoning_mode,
                    reasoning_effort=self.reasoning_effort,
                    reasoning_max_tokens=self.reasoning_max_tokens,
                )
                return resp, eng.provider, eng.model
            except Exception as e:
                last_err = e
                continue
        raise RuntimeError(
            f"All providers failed for {self.model_key!r}: {last_err}"
        )


def _reasoning_from_spec(raw: dict[str, Any], cfg: dict[str, Any]) -> tuple[str, str, int | None]:
    mode = _normalize_reasoning_mode(
        raw.get("reasoning", raw.get("reasoning_mode", cfg.get("reasoning_mode", "off")))
    )
    effort = str(
        raw.get("reasoning_effort", cfg.get("reasoning_effort", "high"))
    ).strip().lower()
    max_tok = raw.get("reasoning_max_tokens", cfg.get("reasoning_max_tokens"))
    return mode, effort, int(max_tok) if max_tok is not None else None


def resolve_models(cfg: dict[str, Any]) -> dict[str, ModelSpec]:
    """
    Parse run.yaml models into model_key -> ModelSpec.

    DeepSeek v4 pro + reasoning example:
      deepseek_v4_pro:
        provider: deepseek
        model: deepseek-v4-pro
        reasoning: on
        reasoning_effort: high   # or max
    """
    raw = cfg.get("models") or {}
    if not raw:
        return {}

    out: dict[str, ModelSpec] = {}
    for model_key, spec in raw.items():
        chain: list[tuple[str, str]] = []
        reasoning_mode = "off"
        reasoning_effort = "high"
        reasoning_max_tokens: int | None = None

        if isinstance(spec, str):
            chain = [("openrouter", spec)]
        elif isinstance(spec, dict):
            reasoning_mode, reasoning_effort, reasoning_max_tokens = _reasoning_from_spec(spec, cfg)
            if "chain" in spec:
                chain = [
                    (str(item["provider"]), str(item["model"])) for item in spec["chain"]
                ]
            elif "provider" in spec and "model" in spec:
                chain = [(str(spec["provider"]), str(spec["model"]))]
            else:
                raise ValueError(
                    f"models.{model_key}: need slug string, {{provider, model}}, or chain"
                )
        elif isinstance(spec, list):
            chain = [(str(item["provider"]), str(item["model"])) for item in spec]
        else:
            raise ValueError(f"Invalid models.{model_key} spec: {spec!r}")

        for provider, _ in chain:
            if provider not in PROVIDER_CONFIGS:
                raise ValueError(
                    f"Unknown provider {provider!r} for {model_key}; "
                    f"expected one of {list(PROVIDER_CONFIGS)}"
                )

        out[model_key] = ModelSpec(
            key=model_key,
            chain=chain,
            reasoning_mode=reasoning_mode,
            reasoning_effort=reasoning_effort,
            reasoning_max_tokens=reasoning_max_tokens,
        )
    return out


def resolve_model_chains(cfg: dict[str, Any]) -> dict[str, list[tuple[str, str]]]:
    """Backward-compatible chain-only view."""
    return {k: v.chain for k, v in resolve_models(cfg).items()}
