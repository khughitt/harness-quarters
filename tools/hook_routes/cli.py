"""Command line for the hook route table."""
import argparse
from pathlib import Path
import sys

from .render import check_live, render_live
from .table import load


def main(argv):
    parser = argparse.ArgumentParser(prog="hook-routes", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    render = commands.add_parser("render", help="rewrite the tracked hook wiring")
    render.add_argument("--home", type=Path, default=Path.home(), help="home used in relay commands")
    commands.add_parser("check", help="check tracked hook wiring against the table")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    path = root / "harnesses/hook-routes.toml"
    try:
        table = load(path)
        if args.command == "check":
            findings = check_live(table, Path.home())
            for finding in findings:
                print(f"{finding.where}: {finding.code}: {finding.message}", file=sys.stderr)
            return int(bool(findings))
        for name, data in render_live(table, args.home).items():
            destination = root / name
            if not destination.exists() or destination.read_bytes() != data:
                destination.write_bytes(data)
    except (OSError, KeyError, TypeError, ValueError) as error:
        print(f"hook-routes: {error}", file=sys.stderr)
        return 1
    return 0
