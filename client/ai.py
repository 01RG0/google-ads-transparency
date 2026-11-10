from __future__ import annotations

import os

import httpx


PROVIDERS: dict[str, dict[str, str | None]] = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "env_var": "GROQ_API_KEY",
        "default_model": None,  # auto-detected at runtime
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "env_var": "OPENAI_API_KEY",
        "default_model": None,
    },
    "together": {
        "base_url": "https://api.together.xyz/v1",
        "env_var": "TOGETHER_API_KEY",
        "default_model": None,
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "env_var": None,
        "default_model": None,
    },
    "anthropic": {
        "base_url": None,
        "env_var": "ANTHROPIC_API_KEY",
        "default_model": None,
    },
}

# Anthropic models endpoint is different — handled separately
_ANTHROPIC_MODELS_URL = "https://api.anthropic.com/v1/models"


async def _fetch_first_model(base_url: str, api_key: str | None, provider: str) -> str:
    """Fetch the first available model from the provider's /models endpoint."""
    if provider == "anthropic":
        url = _ANTHROPIC_MODELS_URL
        headers = {"x-api-key": api_key or "", "anthropic-version": "2023-06-01"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=10.0)
        if resp.status_code != 200:
            raise RuntimeError(f"Could not fetch Anthropic models (HTTP {resp.status_code}). Pass --model explicitly.")
        data = resp.json()
        models = [m["id"] for m in data.get("data", [])]
    else:
        url = f"{base_url}/models"
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=10.0)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Could not auto-detect model for {provider} (HTTP {resp.status_code}). "
                "Pass --model explicitly."
            )
        data = resp.json()
        models = [m["id"] for m in data.get("data", [])]

    # filter out non-text models (embeddings, whisper, guard, tts, etc.)
    _skip = ("whisper", "embed", "guard", "tts", "vision", "image", "speech",
             "safeguard", "prompt-guard", "orpheus", "allam")
    text_models = [m for m in models if not any(s in m.lower() for s in _skip)]
    chosen = text_models[0] if text_models else (models[0] if models else None)
    if chosen is None:
        raise RuntimeError(f"No models found for {provider}. Pass --model explicitly.")
    return chosen


def list_providers() -> list[str]:
    return list(PROVIDERS.keys())


async def ai_complete(
    prompt: str,
    *,
    provider: str,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    system: str = "You are a helpful marketing analyst.",
) -> str:
    provider_lower = provider.lower()
    provider_info = PROVIDERS.get(provider_lower)

    if provider_info is None:
        if base_url is None:
            raise ValueError(
                f"Unknown provider {provider!r}. Known: {list(PROVIDERS)} or pass base_url="
            )
        provider_info = {"base_url": base_url, "env_var": None, "default_model": model}

    resolved_base_url = base_url or os.environ.get("AI_BASE_URL") or provider_info["base_url"]
    if resolved_base_url is None:
        raise ValueError(f"No base_url configured for provider {provider!r}")

    resolved_model = model or os.environ.get("AI_MODEL") or provider_info["default_model"]
    if resolved_model is None:
        # auto-detect from the provider's /models endpoint
        resolved_model = await _fetch_first_model(
            resolved_base_url, resolved_api_key, provider_lower
        )

    env_var = provider_info["env_var"]
    resolved_api_key = api_key
    if resolved_api_key is None and env_var is not None:
        resolved_api_key = os.environ.get(env_var)
    if resolved_api_key is None:
        resolved_api_key = os.environ.get("AI_API_KEY")

    if provider_lower != "ollama" and resolved_api_key is None:
        raise ValueError(
            f"No API key found for {provider}. Set {env_var} environment variable or pass api_key="
        )

    if provider_lower == "anthropic":
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": resolved_api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        body = {
            "model": resolved_model,
            "max_tokens": 1024,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
    else:
        url = f"{resolved_base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if resolved_api_key is not None:
            headers["Authorization"] = f"Bearer {resolved_api_key}"
        body = {
            "model": resolved_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
        }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=body, timeout=60.0)

    if response.status_code != 200:
        raise RuntimeError(
            f"AI provider {provider} returned HTTP {response.status_code}: {response.text[:200]}"
        )

    data = response.json()

    if provider_lower == "anthropic":
        return data["content"][0]["text"]
    return data["choices"][0]["message"]["content"]