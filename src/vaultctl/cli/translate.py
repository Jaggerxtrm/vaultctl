from __future__ import annotations

from argparse import Namespace

from vaultctl.cli.output import emit
from vaultctl.services.translate_service import translate_path

TRANSLATE_DESCRIPTION = (
    "Translate a markdown file while preserving frontmatter, code blocks, and wikilinks."
)

TRANSLATE_EPILOG = """Requirements:
  - Install LLM dependencies: pip install .[llm]
  - Set provider credentials with environment variables:
      VAULTCTL_LLM_PROVIDER   (e.g. openai, anthropic, openrouter)
      VAULTCTL_LLM_API_KEY    (provider API key)
      VAULTCTL_LLM_BASE_URL   (optional custom endpoint)

Example (Italian -> English for better FTS5 search coverage):
  vaultctl translate notes/ricerca.md --target en --output notes/en
"""


def run(args: Namespace) -> None:
    result = translate_path(path=args.path, target_language=args.target, output_dir=args.output)
    emit(result, args.json)
