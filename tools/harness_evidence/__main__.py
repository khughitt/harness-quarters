"""Command line for standalone harness evidence decoding."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from . import DECODER_VERSION, SCHEMA, RevisionUnknown, revision


def _root(value: str) -> tuple[str, Path]:
    harness, separator, path = value.partition("=")
    if not separator or not path or harness not in ("claude-code", "codex", "agy"):
        raise argparse.ArgumentTypeError("root must be claude-code=PATH, codex=PATH or agy=PATH")
    return harness, Path(path)


def _file_facts(place) -> tuple[dict | None, dict | None]:
    """Path facts and the side-input fingerprint from one snapshot of them."""
    from . import discover
    from .index_adapters import ADAPTERS
    adapter = ADAPTERS.get(place.harness)
    if adapter is None:
        return discover.path_facts(place), None
    facts = adapter.path_facts(place)
    return facts, adapter.side_inputs(facts)


def _discover(args: argparse.Namespace, envelope: dict) -> None:
    from . import discover

    roots = discover.roots(args.home, args.root)
    listing = discover.list_files(roots, None)
    for root, entry in zip(roots, listing.roots):
        aliases = []
        for path in listing.aliases:
            if discover._root_of(path, roots) != root:
                continue
            place = discover.place_of(path, roots)
            location = asdict(place)
            del location["path"]
            del location["read_path"]
            aliases.append({"path": str(path), "place": location,
                            "filename_identity": discover.filename_identity(place.harness, path),
                            "filename_lookup": discover.filename_lookup(place.harness, path, root=root),
                            "path_facts": discover.path_facts(place)})
        print(json.dumps({**envelope, "object": "root", "path": str(root.path), **entry,
                          "aliases": aliases}))
    for path in listing.files:
        place = discover.place_of(path, roots)
        location = asdict(place)
        del location["path"]
        del location["read_path"]
        facts, side_inputs = _file_facts(place)
        output = {**envelope, "object": "file", "path": str(path), "harness": place.harness,
                  "device": None, "inode": None, "size": None, "mtime_ns": None,
                  "place": location, "filename_identity": discover.filename_identity(place.harness, path),
                  "filename_lookup": discover.filename_lookup(place.harness, path, root=discover._root_of(path, roots)),
                  "path_facts": facts, "side_inputs": side_inputs,
                  "copy": discover.copy_label(place.harness, path), "state": "listed"}
        try:
            if path in listing.file_errors:
                raise listing.file_errors[path]
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
    capabilities_parser = commands.add_parser("capabilities", help="show catalogued decoder evidence")
    mode = capabilities_parser.add_mutually_exclusive_group()
    mode.add_argument("--json", action="store_true")
    mode.add_argument("--build", action="store_true", help="rebuild the committed artifact in an hq checkout")
    discover_parser = commands.add_parser("discover", help="list transcript paths and metadata")
    discover_parser.add_argument("--home", type=Path)
    discover_parser.add_argument("--root", type=_root, action="append")
    commands.add_parser("decode", help="decode framed JSON requests from stdin")
    commands.add_parser("header", help="select bounded Claude headers from stdin")
    args = parser.parse_args(argv)
    if args.command == "capabilities":
        from . import capabilities
        try:
            if args.build:
                capabilities.build_artifact()
            else:
                value = capabilities.view({"version": DECODER_VERSION, "revision": revision()})
                print(json.dumps(value, sort_keys=True) if args.json else capabilities.table(value))
        except (OSError, ValueError, KeyError, RevisionUnknown) as error:
            print(f"capabilities: {error}", file=sys.stderr)
            return 2
        return 0
    try:
        output = {"schema": SCHEMA, "decoder": {"version": DECODER_VERSION, "revision": revision()}}
    except RevisionUnknown as error:
        print(str(error), file=sys.stderr)
        return 2
    if args.command == "header":
        from .header import run
        return run(sys.stdin, sys.stdout, sys.stderr, output)
    if args.command == "decode":
        from .stream import run
        return run(sys.stdin, sys.stdout, sys.stderr, output)
    if args.command == "discover":
        _discover(args, output)
    else:
        print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
