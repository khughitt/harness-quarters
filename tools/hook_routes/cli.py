"""Command line for the hook route table."""
import argparse
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

from .deploy import deploy, live_files, reconcile_base, review_files
from .preflight import installed_versions, run as preflight
from .qualification import qualification_findings
from .references import changed_codex_entries, donor_references
from .render import check_live, render_candidate, render_live, render_next
from .rules import route_status, validate
from .table import load

__all__ = ["main"]


def _report(findings):
    for finding in findings:
        print(f"{finding.where}: {finding.code}: {finding.message}", file=sys.stderr)
    return int(bool(findings))


def _write_review(out, files, *, candidate):
    if candidate:
        manifest = {
            "kind": "candidate",
            "files": {path: sha256(data).hexdigest() for path, data in sorted(files.items())},
        }
        files = {**files, "manifest.json": (json.dumps(manifest, indent=2) + "\n").encode()}
    out = out.absolute()
    if out.is_symlink():
        raise ValueError(f"review directory cannot be a symlink: {out}")
    out.mkdir(parents=True, exist_ok=True)
    out = out.resolve()
    if any(out.iterdir()):
        raise ValueError(f"review directory must be empty: {out}")
    for name, data in files.items():
        destination = out / name
        if not destination.resolve().is_relative_to(out):
            raise ValueError(f"review output is outside its directory: {name}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as target:
            target.write(data)


def _render(args, table):
    if args.variant == "next":
        _write_review(args.out, render_next(table, args.home), candidate=False)
    elif args.variant == "candidate":
        _write_review(args.out, render_candidate(table, args.slice, args.home), candidate=True)
    else:
        findings = validate(table, home=args.home)
        if findings:
            return _report(findings)
        for name, data in render_live(table, args.home).items():
            destination = table.root / name
            if not destination.exists() or destination.read_bytes() != data:
                destination.write_bytes(data)
    return 0


def _status(args, table):
    if args.donor is not None:
        for ref in donor_references(table, args.donor):
            print(f"{ref.kind}\t{ref.where}")
    elif args.changed_codex_entries:
        for entry in changed_codex_entries(table.root, args.base, render_live(table, Path.home())):
            print(entry)
    else:
        routes = route_status(table)
        for route in routes:
            print(json.dumps(asdict(route)))
        versions = {}
        if any(state and state.kind == "relay" for r in routes for state in (r.state, r.next)):
            versions = installed_versions(os.environ.get("PATH", os.defpath))
        for finding in qualification_findings(table, versions=versions):
            print(json.dumps(asdict(finding)))
    return 0


def main(argv):
    parser = argparse.ArgumentParser(prog="hook-routes", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    render = commands.add_parser("render", help="rewrite tracked wiring or render a proposed cutover")
    render.add_argument("--home", type=Path, default=Path.home(), help="home used in relay commands")
    variants = render.add_subparsers(dest="variant")
    next_render = variants.add_parser("next", help="render the table's proposed cutover into a review directory")
    candidate = variants.add_parser("candidate", help="render a candidate slice for qualification")
    candidate.add_argument("slice", type=Path)
    for variant in (next_render, candidate):
        variant.add_argument("--out", type=Path, required=True)
        variant.add_argument("--home", type=Path, default=argparse.SUPPRESS)
    commands.add_parser("check", help="check tracked hook wiring against the table")
    deploy_cmd = commands.add_parser("deploy", help="install live or reviewed target subscriber files")
    deploy_modes = deploy_cmd.add_subparsers(dest="variant", required=True)
    deploy_modes.add_parser("live")
    deploy_modes.add_parser("next").add_argument("directory", type=Path)
    commands.add_parser("reconcile-base", help="show the live relay reconciliation config base")
    commands.add_parser("preflight", help="check the installed host").add_argument("--next", type=Path)
    status = commands.add_parser("status", help="show route states, donor references or changed Codex trust keys")
    modes = status.add_mutually_exclusive_group()
    modes.add_argument("--donor", metavar="PATH")
    modes.add_argument("--changed-codex-entries", action="store_true")
    status.add_argument("--base", metavar="REF")

    args = parser.parse_args(argv)
    if args.command == "status" and bool(args.base) != args.changed_codex_entries:
        status.error("--changed-codex-entries and --base REF must be used together")
    root = Path(__file__).resolve().parents[2]
    path = root / "harnesses/hook-routes.toml"
    try:
        table = load(path)
        if args.command == "check":
            findings = validate(table)
            return _report(findings or qualification_findings(table) + check_live(table, Path.home()))
        if args.command == "reconcile-base":
            print(reconcile_base(table, Path.home()))
            return 0
        if args.command == "deploy":
            findings = validate(table)
            if findings:
                return _report(findings)
            home = Path.home()
            files = live_files(table, home) if args.variant == "live" else review_files(table, home, args.directory)
            for path in deploy(files, home):
                print(path)
            return 0
        if args.command == "preflight":
            return _report(preflight(table, home=Path.home(), path_env=os.environ.get("PATH", os.defpath),
                                     next_dir=args.next))
        if args.command == "status":
            return _status(args, table)
        return _render(args, table)
    except (OSError, KeyError, TypeError, ValueError) as error:
        print(f"hook-routes: {error}", file=sys.stderr)
        return 1
