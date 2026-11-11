"""Command line for standalone harness evidence decoding."""
import argparse
import json
import sys

from . import DECODER_VERSION, SCHEMA, RevisionUnknown, revision


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harness-evidence")
    commands = parser.add_subparsers(dest="command", required=True)
    version = commands.add_parser("version", help="identify the decoder")
    version.add_argument("--json", action="store_true", required=True)
    parser.parse_args(argv)
    try:
        output = {"schema": SCHEMA, "decoder": {"version": DECODER_VERSION, "revision": revision()}}
    except RevisionUnknown as error:
        print(str(error), file=sys.stderr)
        return 2
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
