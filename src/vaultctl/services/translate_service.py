from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from vaultctl.core.errors import NotFoundError, TranslationError
from vaultctl.core.llm import LLMClient, load_llm_settings
from vaultctl.core.paths import ensure_parent

FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
FENCED_BLOCK_RE = re.compile(r"```[^\n]*\n.*?\n```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
WIKILINK_RE = re.compile(r"\[\[[^\]]+\]\]")
TOKEN_RE = re.compile(r"@@VAULTCTL_[A-Z]+_(\d+)@@")


@dataclass(frozen=True)
class TranslationOutcome:
    source_path: Path
    output_path: Path


def translate_path(path: str, target_language: str, output_dir: str | None = None) -> dict[str, object]:
    source_path = Path(path).expanduser()
    if not source_path.exists():
        raise NotFoundError(f"Path does not exist: {source_path}")

    markdown_files = _collect_markdown_files(source_path)
    settings = load_llm_settings()
    llm_client = LLMClient(settings)

    output_root = Path(output_dir).expanduser() if output_dir else None
    outcomes: list[TranslationOutcome] = []
    for markdown_path in markdown_files:
        translated = _translate_markdown_file(markdown_path, target_language, llm_client)
        destination = _resolve_destination(source_path, markdown_path, output_root)
        ensure_parent(destination)
        destination.write_text(translated, encoding="utf-8")
        outcomes.append(TranslationOutcome(source_path=markdown_path, output_path=destination))

    return {
        "target": target_language,
        "provider": settings.provider,
        "model": settings.model,
        "translated": len(outcomes),
        "files": [
            {
                "source": str(outcome.source_path),
                "output": str(outcome.output_path),
            }
            for outcome in outcomes
        ],
    }


def _collect_markdown_files(source_path: Path) -> tuple[Path, ...]:
    if source_path.is_file():
        if source_path.suffix.lower() != ".md":
            raise TranslationError(f"Expected a markdown file (.md): {source_path}")
        return (source_path,)

    markdown_files = tuple(sorted(path for path in source_path.rglob("*.md") if path.is_file()))
    if not markdown_files:
        raise TranslationError(f"No markdown files found in directory: {source_path}")
    return markdown_files


def _resolve_destination(source_root: Path, markdown_path: Path, output_root: Path | None) -> Path:
    if output_root is None:
        return markdown_path

    if source_root.is_file():
        return output_root / markdown_path.name

    relative_path = markdown_path.relative_to(source_root)
    return output_root / relative_path


def _translate_markdown_file(markdown_path: Path, target_language: str, llm_client: LLMClient) -> str:
    source_content = markdown_path.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(source_content)
    masked_body, token_map = _mask_non_prose_segments(body)
    translated_body = llm_client.translate(masked_body, target_language)
    _validate_tokens(translated_body, token_map)
    restored_body = _restore_tokens(translated_body, token_map)
    return f"{frontmatter}{restored_body}"


def _split_frontmatter(content: str) -> tuple[str, str]:
    match = FRONTMATTER_RE.match(content)
    if match is None:
        return "", content
    return match.group(0), content[match.end() :]


def _mask_non_prose_segments(content: str) -> tuple[str, dict[str, str]]:
    token_map: dict[str, str] = {}
    masked = content

    for token_type, pattern in (
        ("FENCE", FENCED_BLOCK_RE),
        ("INLINE", INLINE_CODE_RE),
        ("WIKILINK", WIKILINK_RE),
    ):
        masked = _mask_pattern(masked, pattern, token_type, token_map)

    return masked, token_map


def _mask_pattern(content: str, pattern: re.Pattern[str], token_type: str, token_map: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        token = f"@@VAULTCTL_{token_type}_{len(token_map)}@@"
        token_map[token] = match.group(0)
        return token

    return pattern.sub(replace, content)


def _validate_tokens(content: str, token_map: dict[str, str]) -> None:
    present_tokens = set(TOKEN_RE.finditer(content))
    present_token_values = {match.group(0) for match in present_tokens}
    expected_tokens = set(token_map.keys())
    if present_token_values != expected_tokens:
        raise TranslationError("Translation did not preserve protected markdown segments")


def _restore_tokens(content: str, token_map: dict[str, str]) -> str:
    restored = content
    for token, original in token_map.items():
        restored = restored.replace(token, original)
    return restored
