from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from openai import OpenAI

from vaultctl.core.errors import LLMConfigError, LLMRequestError

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_ANTHROPIC_MODEL = "claude-3-5-sonnet-latest"
DEFAULT_ANTHROPIC_BASE_URL = "https://api.anthropic.com"


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    api_key: str
    base_url: str | None
    model: str


def load_llm_settings() -> LLMSettings:
    provider = os.getenv("VAULTCTL_LLM_PROVIDER", "openai").strip().lower()
    api_key = os.getenv("VAULTCTL_LLM_API_KEY", "").strip()
    base_url = os.getenv("VAULTCTL_LLM_BASE_URL")
    model = os.getenv("VAULTCTL_LLM_MODEL", "").strip()

    if not api_key:
        raise LLMConfigError("Missing VAULTCTL_LLM_API_KEY")

    if provider == "openai":
        return LLMSettings(
            provider=provider,
            api_key=api_key,
            base_url=base_url.strip() if isinstance(base_url, str) and base_url.strip() else None,
            model=model or DEFAULT_OPENAI_MODEL,
        )

    if provider == "anthropic":
        normalized_base_url = base_url.strip() if isinstance(base_url, str) and base_url.strip() else DEFAULT_ANTHROPIC_BASE_URL
        return LLMSettings(
            provider=provider,
            api_key=api_key,
            base_url=normalized_base_url,
            model=model or DEFAULT_ANTHROPIC_MODEL,
        )

    raise LLMConfigError(f"Unsupported VAULTCTL_LLM_PROVIDER: {provider}")


class LLMClient:
    def __init__(self, settings: LLMSettings) -> None:
        self._settings = settings
        self._openai_client = OpenAI(api_key=settings.api_key, base_url=settings.base_url) if settings.provider == "openai" else None

    def translate(self, text: str, target_language: str) -> str:
        if self._settings.provider == "openai":
            return self._translate_openai(text, target_language)
        if self._settings.provider == "anthropic":
            return self._translate_anthropic(text, target_language)
        raise LLMRequestError(f"Unsupported LLM provider: {self._settings.provider}")

    def _translate_openai(self, text: str, target_language: str) -> str:
        if self._openai_client is None:
            raise LLMRequestError("OpenAI client is not initialized")
        try:
            response = self._openai_client.chat.completions.create(
                model=self._settings.model,
                temperature=0,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Translate markdown prose only. Preserve markdown syntax, spacing, and placeholders exactly "
                            "as provided. Return only the translated markdown text."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Target language: {target_language}\n\n{text}",
                    },
                ],
            )
        except Exception as exc:  # pragma: no cover - network/API failures
            raise LLMRequestError(f"OpenAI request failed: {exc}") from exc

        message = response.choices[0].message.content if response.choices else None
        if not isinstance(message, str) or not message.strip():
            raise LLMRequestError("OpenAI returned empty translation response")
        return message

    def _translate_anthropic(self, text: str, target_language: str) -> str:
        base_url = self._settings.base_url
        if base_url is None:
            raise LLMRequestError("Anthropic base URL is not configured")

        payload: dict[str, Any] = {
            "model": self._settings.model,
            "max_tokens": 8192,
            "temperature": 0,
            "system": (
                "Translate markdown prose only. Preserve markdown syntax, spacing, and placeholders exactly "
                "as provided. Return only the translated markdown text."
            ),
            "messages": [
                {
                    "role": "user",
                    "content": f"Target language: {target_language}\n\n{text}",
                }
            ],
        }

        req = request.Request(
            url=f"{base_url.rstrip('/')}/v1/messages",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "content-type": "application/json",
                "x-api-key": self._settings.api_key,
                "anthropic-version": "2023-06-01",
            },
        )

        try:
            with request.urlopen(req) as response:
                body = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:  # pragma: no cover - network/API failures
            details = exc.read().decode("utf-8", errors="ignore")
            raise LLMRequestError(f"Anthropic request failed: HTTP {exc.code}: {details}") from exc
        except Exception as exc:  # pragma: no cover - network/API failures
            raise LLMRequestError(f"Anthropic request failed: {exc}") from exc

        content = body.get("content")
        if not isinstance(content, list):
            raise LLMRequestError("Anthropic response did not include content")

        text_blocks = [block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text"]
        translated = "".join(text_blocks).strip()
        if not translated:
            raise LLMRequestError("Anthropic returned empty translation response")
        return translated
