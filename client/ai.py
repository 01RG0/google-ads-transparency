from __future__ import annotations

import os

import httpx


PROVIDERS: dict[str, dict[str, str | None]] = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "env_var": "GROQ_API_KEY",
        "default_model": "llama-3.3-70b-versatile",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "env_var": "OPENAI_API_KEY",
        "default_model": "gpt-4o-mini",
    },
    "together": {
        "base_url": "https://api.together.xyz/v1",
        "env_var": "TOGETHER_API_KEY",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "env_var": None,
        "default_model": "llama3.2",
    },
    "anthropic": {
        "base_url": None,
        "env_var": "ANTHROPIC_API_KEY",
        "default_model": "claude-haiku-5-5",
    },
}


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
        raise ValueError(f"No model configured for provider {provider!r}")

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