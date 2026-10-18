"""Invocação local do handler lendo um evento JSON da entrada padrão."""

import json
import sys
from collections.abc import Mapping

from lambda_auth.handler import lambda_handler


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.stderr.write("A entrada precisa ser um objeto JSON válido.\n")
        return 2

    if not isinstance(event, Mapping):
        sys.stderr.write("A entrada precisa ser um objeto JSON válido.\n")
        return 2

    json.dump(lambda_handler(event, None), sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
