"""Command line for standalone harness evidence decoding."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from . import DECODER_VERSION, SCHEMA, RevisionUnknown, revision


def _root(value: str) -> tuple[str, Path]:
    harness, separator, path = value.partition("=")
    if not separator or not path or harness not in ("claude-code", "codex"):
        raise argparse.ArgumentTypeError("root must be claude-code=PATH or codex=PATH")
    return harness, Path(path)


def _discover(args: argparse.Namespace, envelope: dict) -> None:
    from . import discover

    roots = discover.roots(args.home, args.root)
    listing = discover.list_files(roots, None)
    for root, entry in zip(roots, listing.roots):
        print(json.dumps({**envelope, "object": "root", "path": str(root.path), **entry}))
    for path in listing.files:
        place = discover.place_of(path, roots)
        location = asdict(place)
        del location["path"]
        output = {**envelope, "object": "file", "path": str(path), "harness": place.harness,
                  "device": None, "inode": None, "size": None, "mtime_ns": None,
                  "place": location, "filename_identity": discover.filename_identity(place.harness, path),
                  "state": "listed"}
        try:
            info = path.stat()
        except OSError as error:
            output.update(state="vanished" if isinstance(error, FileNotFoundError) else "unreadable",
                          error=f"{type(error).__name__}: {error}")
        else:
            output.update(device=info.st_dev, inode=info.st_ino, size=info.st_size, mtime_ns=info.st_mtime_ns)
        print(json.dumps(output))
    print(json.dumps({**envelope, "object": "discover_end", "roots": len(roots), "files": len(listing.files)}))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harness-evidence")
    commands = parser.add_subparsers(dest="command", required=True)
    version = commands.add_parser("version", help="identify the decoder")
    version.add_argument("--json", action="store_true", required=True)
    discover_parser = commands.add_parser("discover", help="list transcript paths and metadata")
    discover_parser.add_argument("--home", type=Path)
    discover_parser.add_argument("--root", type=_root, action="append")
    args = parser.parse_args(argv)
    try:
        output = {"schema": SCHEMA, "decoder": {"version": DECODER_VERSION, "revision": revision()}}
    except RevisionUnknown as error:
        print(str(error), file=sys.stderr)
        return 2
    if args.command == "discover":
        _discover(args, output)
    else:
        print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
