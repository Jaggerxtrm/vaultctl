from __future__ import annotations

import re
from dataclasses import dataclass

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
TAG_LINE_RE = re.compile(r"^tags\s*:\s*(.+)$", re.MULTILINE)
STATUS_RE = re.compile(r"^status\s*:\s*(.+)$", re.MULTILINE)
TITLE_RE = re.compile(r"^title\s*:\s*(.+)$", re.MULTILINE)
ALIASES_SCALAR_RE = re.compile(r"^aliases\s*:\s*(.+)$", re.MULTILINE)
ALIASES_LIST_RE = re.compile(r"^aliases\s*:\s*$", re.MULTILINE)
ALIASES_ITEM_RE = re.compile(r"^\s*-\s*(.+)$")


@dataclass(frozen=True)
class ParsedLink:
    raw: str
    target: str
    fragment: str | None
    display: str | None


@dataclass(frozen=True)
class ParsedMarkdown:
    title: str
    body: str
    tags: tuple[str, ...]
    status: str | None
    links: tuple[ParsedLink, ...]
    heading_paths: tuple[str, ...]
    aliases: tuple[str, ...]


def _strip_quotes(value: str) -> str:
    return value.strip().strip('"').strip("'")


def _parse_aliases(frontmatter: str) -> tuple[str, ...]:
    aliases: list[str] = []

    scalar_match = ALIASES_SCALAR_RE.search(frontmatter)
    if scalar_match:
        raw = scalar_match.group(1).strip()
        if raw.startswith("[") and raw.endswith("]"):
            values = raw[1:-1].split(",")
            aliases.extend(_strip_quotes(value) for value in values if value.strip())
        elif raw:
            aliases.append(_strip_quotes(raw))
        return tuple(sorted({alias for alias in aliases if alias}))

    list_match = ALIASES_LIST_RE.search(frontmatter)
    if not list_match:
        return ()

    lines = frontmatter[list_match.end() :].splitlines()
    for line in lines:
        if line and not line.startswith(" "):
            break
        item_match = ALIASES_ITEM_RE.match(line)
        if not item_match:
            continue
        alias = _strip_quotes(item_match.group(1))
        if alias:
            aliases.append(alias)

    return tuple(sorted(set(aliases)))


def _parse_link(raw: str) -> ParsedLink:
    body = raw.strip()
    target_part, display_part = (body.split("|", 1) + [None])[:2] if "|" in body else (body, None)
    target_text = target_part.strip()
    fragment: str | None = None
    if "#" in target_text:
        target_text, fragment = target_text.split("#", 1)
        target_text = target_text.strip()
        fragment = fragment.strip() or None

    display = display_part.strip() if display_part is not None else None
    if display == "":
        display = None

    return ParsedLink(raw=raw, target=target_text, fragment=fragment, display=display)


def parse_markdown(content: str, fallback_title: str) -> ParsedMarkdown:
    body = content
    frontmatter = ""
    frontmatch = FRONTMATTER_RE.match(content)
    if frontmatch:
        frontmatter = frontmatch.group(1)
        body = content[frontmatch.end() :]

    title_match = TITLE_RE.search(frontmatter)
    title = (title_match.group(1).strip() if title_match else fallback_title).strip('"')

    tags_match = TAG_LINE_RE.search(frontmatter)
    tags = ()
    if tags_match:
        tag_values = tags_match.group(1).strip().strip("[]")
        tags = tuple(sorted({tag.strip().strip('"').strip("'") for tag in tag_values.split(",") if tag.strip()}))

    status_match = STATUS_RE.search(frontmatter)
    status = status_match.group(1).strip().strip('"') if status_match else None

    links = tuple(_parse_link(match.group(1).strip()) for match in WIKILINK_RE.finditer(body))
    heading_paths = tuple(match.group(2).strip() for match in HEADING_RE.finditer(body))
    aliases = _parse_aliases(frontmatter)

    return ParsedMarkdown(
        title=title,
        body=body,
        tags=tags,
        status=status,
        links=links,
        heading_paths=heading_paths,
        aliases=aliases,
    )
