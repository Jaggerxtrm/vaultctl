from __future__ import annotations

from argparse import Namespace

from vaultctl.cli.output import emit
from vaultctl.services.translate_service import translate_path


def run(args: Namespace) -> None:
    result = translate_path(path=args.path, target_language=args.target, output_dir=args.output)
    emit(result, args.json)
