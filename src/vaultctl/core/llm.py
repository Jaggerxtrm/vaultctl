from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from vaultctl.core.errors import LLMConfigError, LLMRequestError

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-3-5"
DEFAULT_ANTHROPIC_BASE_URL = "https://api.anthropic.com"
TRANSLATION_SYSTEM_PROMPT = (
    "Translate markdown prose only. Preserve markdown syntax, spacing, and placeholders exactly "
    "as provided. Return only the translated markdown text."
)


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    api_key: str
    base_url: str | None
    model: str


def load_llm_settings() -> LLMSettings:
    provider = os.getenv("VAULTCTL_LLM_PROVIDER", "openai").strip().lower()
    api_key = os.getenv("VAULTCTL_LLM_API_KEY", "").strip()
    base_url = _read_optional_env("VAULTCTL_LLM_BASE_URL")
    model = _read_optional_env("VAULTCTL_LLM_MODEL")

    if not api_key:
        raise LLMConfigError("Missing VAULTCTL_LLM_API_KEY")

    if provider == "openai":
        return LLMSettings(provider=provider, api_key=api_key, base_url=base_url, model=model or DEFAULT_OPENAI_MODEL)

    if provider == "anthropic":
        return LLMSettings(
            provider=provider,
            api_key=api_key,
            base_url=base_url or DEFAULT_ANTHROPIC_BASE_URL,
            model=model or DEFAULT_ANTHROPIC_MODEL,
        )

    raise LLMConfigError(f"Unsupported VAULTCTL_LLM_PROVIDER: {provider}")


def _read_optional_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    normalized = value.strip()
    return normalized if normalized else None


class LLMClient:
    def __init__(self, settings: LLMSettings) -> None:
        self._settings = settings
        self._client: Any = self._build_client(settings)

    def translate(self, text: str, target_language: str) -> str:
        if self._settings.provider == "openai":
            return self._translate_openai(text, target_language)
        if self._settings.provider == "anthropic":
            return self._translate_anthropic(text, target_language)
        raise LLMRequestError(f"Unsupported LLM provider: {self._settings.provider}")

    def _build_client(self, settings: LLMSettings) -> Any:
        if settings.provider == "openai":
            return _create_openai_client(settings.api_key, settings.base_url)
        if settings.provider == "anthropic":
            return _create_anthropic_client(settings.api_key, settings.base_url)
        raise LLMRequestError(f"Unsupported LLM provider: {settings.provider}")

    def _translate_openai(self, text: str, target_language: str) -> str:
        try:
            response = self._client.chat.completions.create(
                model=self._settings.model,
                temperature=0,
                messages=[
                    {"role": "system", "content": TRANSLATION_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Target language: {target_language}\n\n{text}"},
                ],
            )
        except Exception as exc:  # pragma: no cover - network/API failures
            raise LLMRequestError(f"OpenAI request failed: {exc}") from exc

        message = response.choices[0].message.content if response.choices else None
        if not isinstance(message, str) or not message.strip():
            raise LLMRequestError("OpenAI returned empty translation response")
        return message

    def _translate_anthropic(self, text: str, target_language: str) -> str:
        try:
            response = self._client.messages.create(
                model=self._settings.model,
                max_tokens=8192,
                temperature=0,
                system=TRANSLATION_SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": f"Target language: {target_language}\n\n{text}"},
                ],
            )
        except Exception as exc:  # pragma: no cover - network/API failures
            raise LLMRequestError(f"Anthropic request failed: {exc}") from exc

        translated = "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text" and isinstance(getattr(block, "text", None), str)
        ).strip()
        if not translated:
            raise LLMRequestError("Anthropic returned empty translation response")
        return translated


def _create_openai_client(api_key: str, base_url: str | None) -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - depends on install extras
        raise LLMConfigError("OpenAI provider selected but 'openai' package is not installed") from exc
    return OpenAI(api_key=api_key, base_url=base_url)


def _create_anthropic_client(api_key: str, base_url: str | None) -> Any:
    try:
        from anthropic import Anthropic
    except ImportError as exc:  # pragma: no cover - depends on install extras
        raise LLMConfigError("Anthropic provider selected but 'anthropic' package is not installed") from exc
    return Anthropic(api_key=api_key, base_url=base_url)
