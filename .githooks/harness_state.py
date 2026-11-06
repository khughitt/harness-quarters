"""Mechanics shared by the tools that keep host state in this checkout's live harness configs.

codex-trust and live-picks both rewrite harnesses/codex/config.toml, so they take one host lock,
local/harness-state.lock, around every read-modify-write of a live file or a saved copy.
Separate locks would let a trust restore and a pick restore read the same starting file
and each overwrite the other's insert. Each tool works on the checkout it lives in and
names itself in its failures. Design:
docs/specs/2026-10-10-live-model-preservation-design.md §3.3.
"""
import argparse
import contextlib
import fcntl
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
LOCAL = REPO / "local"
LOCK = LOCAL / "harness-state.lock"
MANIFEST_PATH = REPO / "harnesses.toml"
GITATTRIBUTES_PATH = REPO / ".gitattributes"
EXPECTED_CLEAN_FILTER = ".githooks/harness-state-clean %f"
# Identity smudge: git treats a required filter's missing smudge as fatal on checkout.
EXPECTED_SMUDGE_FILTER = "cat"
FILTER_NAME = "harness-state"
SLUG = re.compile(r"[a-z][a-z0-9-]*")
# Header and key lines of a TOML config, for the line-preserving cleaner.
TOML_HEADER = re.compile(r"^\s*\[\[?\s*(.*?)\s*\]\]?\s*(#.*)?$")
TOML_KEY = re.compile(r'^\s*("[^"]*"|[A-Za-z0-9_-]+)\s*=')
# Directories check_clean_tree never descends into.
TREE_SKIP = frozenset({".git", ".worktrees", ".venv", "node_modules", "local"})
GIT_HOOKS = ("post-checkout", "post-merge", "post-rewrite")
# A rebase runs post-checkout after checking out the new base, then replays commits
# from its in-memory index, which drops a restage made there; the file keeps its new
# size, and the replay of a commit that touches it stops with "local changes would be
# overwritten". post-rewrite restores when the rebase ends.
REBASE_STATE = ("rebase-merge", "rebase-apply")


def write(path, text):
    """Replace path by one rename, keeping its mode: the live configs are private (0600)."""
    mode = path.stat().st_mode & 0o7777 if path.exists() else 0o600
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w") as out:
            out.write(text)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


class Checkout:
    """This checkout's git state as one tool sees it: failures carry the tool's name."""

    def __init__(self, tool):
        self.tool = tool

    def fail(self, message):
        sys.exit(f"{self.tool}: {message}")

    def git(self, *args):
        result = subprocess.run(["git", "-C", str(REPO), *args], text=True, capture_output=True)
        if result.returncode != 0:
            self.fail(f"git {' '.join(args)}: {result.stderr.strip()}")
        return result.stdout.strip()

    def git_path(self, name):
        return Path(self.git("rev-parse", "--path-format=absolute", "--git-path", name))

    def linked_worktree(self):
        return (self.git("rev-parse", "--path-format=absolute", "--git-dir")
                != self.git("rev-parse", "--path-format=absolute", "--git-common-dir"))

    def rebasing(self):
        return any(self.git_path(state).exists() for state in REBASE_STATE)

    def restage(self, name):
        """Stage a restored file when its filtered diff is empty, as harness-state-refresh does.

        The insert changes the file's size, and git calls a file of another size modified
        without running the filter; a rebase refuses to start on that mark. While another
        git process holds the index, the next turn end's refresh stages it instead.
        """
        if self.git_path("index.lock").exists():
            return
        diff = subprocess.run(["git", "-C", str(REPO), "diff", "--quiet", "--", name],
                              text=True, capture_output=True)
        if diff.returncode not in (0, 1):
            self.fail(f"git diff {name}: {diff.stderr.strip()}")
        if diff.returncode == 0:
            self.git("add", "--", name)

    @contextlib.contextmanager
    def locked(self):
        """Hold the host lock every tool that rewrites a live harness config takes."""
        if not LOCAL.is_dir():
            self.fail("local/ is missing; run `just setup`")
        with open(LOCK, "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield


# --- Manifest: harnesses.toml (design: docs/specs/2026-11-01-harness-manifest-design.md §5) ---


class ManifestError(ValueError):
    """The manifest, .gitattributes, filter config or a tracked config is invalid."""

    def __init__(self, problems):
        if isinstance(problems, str):
            problems = [problems]
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


@dataclass(frozen=True)
class TomlKeyRule:
    table_pattern: str
    table_re: re.Pattern[str]
    keys: tuple[str, ...]


@dataclass(frozen=True)
class LiveStateSpec:
    harness: str
    config: str
    filter_glob: str
    filter_re: re.Pattern[str]
    format: str
    json_clean_keys: tuple[str, ...]
    toml_clean_keys: tuple[TomlKeyRule, ...]
    toml_clean_tables: tuple[re.Pattern[str], ...]
    trust_table: re.Pattern[str] | None
    unrestored_keys: tuple[str, ...]
    picks_record: str | None
    pick_units: tuple[tuple[str, ...], ...]

    @property
    def pick_keys(self):
        return sum(self.pick_units, ())


@dataclass(frozen=True)
class HarnessManifest:
    schema: int
    harnesses: tuple[str, ...]
    by_harness: dict[str, LiveStateSpec | None]
    live_state: tuple[LiveStateSpec, ...]


COMMON_KEYS = {"config", "filter_glob", "format", "clean_keys", "unrestored_keys",
               "picks_record", "pick_units"}
ALLOWED_KEYS = {"json": COMMON_KEYS, "toml": COMMON_KEYS | {"clean_tables", "trust_table"}}


def _string_list(value, label, problems, unique=True):
    """A list of non-empty strings (unique when asked), or None after recording why not."""
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        problems.append(f"{label} must be a list of non-empty strings")
        return None
    if unique and len(set(value)) != len(value):
        problems.append(f"{label} must not repeat a string")
        return None
    return tuple(value)


def _relative_path(value, label, problems, glob):
    """Validate a directory-qualified relative POSIX path (a glob of `*` when glob)."""
    if not isinstance(value, str) or not value:
        problems.append(f"{label} must be a non-empty string")
        return None
    parts = value.split("/")
    bad = None
    if len(parts) < 2:
        bad = "must be directory-qualified (contain a '/')"
    elif any(part in ("", ".", "..") for part in parts):
        bad = "must not have empty, '.' or '..' segments or a leading or trailing '/'"
    elif parts[0] == "local":
        bad = "must be outside local/"
    elif glob and any(c in value for c in "?[]"):
        bad = "may use '*' as its only wildcard"
    elif glob and any(part.count("*") > 1 for part in parts):
        bad = "may hold at most one '*' per '/' segment"
    elif not glob and any(c in value for c in "*?[]"):
        bad = "must not hold glob characters"
    if bad:
        problems.append(f"{label} {value!r} {bad}")
        return None
    return parts


def _glob_regex(parts):
    return re.compile("/".join("[^/]*".join(re.escape(p) for p in part.split("*")) for part in parts))


def _segments_overlap(a, b):
    """Whether two single-`*` glob segments both match some string."""
    a_star, b_star = "*" in a, "*" in b
    if not a_star and not b_star:
        return a == b
    if a_star != b_star:
        pattern, literal = (a, b) if a_star else (b, a)
        prefix, suffix = pattern.split("*")
        return (len(literal) >= len(prefix) + len(suffix)
                and literal.startswith(prefix) and literal.endswith(suffix))
    p1, s1 = a.split("*")
    p2, s2 = b.split("*")
    return ((p1.startswith(p2) or p2.startswith(p1))
            and (s1.endswith(s2) or s2.endswith(s1)))


def _globs_overlap(a, b):
    a_parts, b_parts = a.split("/"), b.split("/")
    return len(a_parts) == len(b_parts) and all(map(_segments_overlap, a_parts, b_parts))


def _compile(pattern, label, problems):
    try:
        return re.compile(pattern)
    except re.error as error:
        problems.append(f"{label} {pattern!r} is not a valid regex: {error}")
        return None


def _parse_toml_rules(value, label, problems):
    if not isinstance(value, list):
        problems.append(f"{label} must be a list of {{ table, keys }} tables")
        return None
    rules, seen, ok = [], set(), True
    for index, rule in enumerate(value):
        here = f"{label}[{index}]"
        if not isinstance(rule, dict) or set(rule) != {"table", "keys"}:
            problems.append(f"{here} must be a table with exactly `table` and `keys`")
            ok = False
            continue
        table, keys = rule["table"], rule["keys"]
        if not isinstance(table, str):
            problems.append(f"{here}.table must be a string")
            ok = False
            continue
        compiled = _compile(table, f"{here}.table", problems)
        keys = _string_list(keys, f"{here}.keys", problems) if keys else None
        if keys is None and not rule["keys"]:
            problems.append(f"{here}.keys must not be empty")
        if compiled is None or keys is None:
            ok = False
            continue
        for key in keys:
            if (table, key) in seen:
                problems.append(f"{label} repeats table {table!r} key {key!r}")
                ok = False
            seen.add((table, key))
        rules.append(TomlKeyRule(table, compiled, keys))
    return tuple(rules) if ok else None


def _parse_live_state(name, table, problems):
    label = f"harnesses.{name}.live_state"
    if not isinstance(table, dict):
        problems.append(f"{label} must be a table")
        return None
    start = len(problems)
    fmt = table.get("format")
    if not isinstance(fmt, str) or fmt not in ALLOWED_KEYS:
        problems.append(f'{label}.format must be "json" or "toml"')
        return None
    for key in sorted(set(table) - ALLOWED_KEYS[fmt]):
        problems.append(f"{label} has unknown key {key!r} for format {fmt!r}")
    for key in ("config", "filter_glob", "clean_keys"):
        if key not in table:
            problems.append(f"{label}.{key} is required")
    if len(problems) > start:
        return None

    config_parts = _relative_path(table["config"], f"{label}.config", problems, glob=False)
    glob_parts = _relative_path(table["filter_glob"], f"{label}.filter_glob", problems, glob=True)
    filter_re = _glob_regex(glob_parts) if glob_parts else None
    if filter_re and config_parts and not filter_re.fullmatch(table["config"]):
        problems.append(f"{label}.config {table['config']!r} does not match filter_glob "
                        f"{table['filter_glob']!r}")

    json_keys, toml_rules, tables, trust = (), (), (), None
    if fmt == "json":
        keys = _string_list(table["clean_keys"], f"{label}.clean_keys", problems)
        if keys is not None and not keys:
            problems.append(f"{label}.clean_keys must not be empty")
        json_keys = keys or ()
        ordered = json_keys
        filterable = set(json_keys)
    else:
        toml_rules = _parse_toml_rules(table["clean_keys"], f"{label}.clean_keys", problems) or ()
        raw_tables = table.get("clean_tables", [])
        names = _string_list(raw_tables, f"{label}.clean_tables", problems) or ()
        compiled = [_compile(n, f"{label}.clean_tables", problems) for n in names]
        tables = tuple(c for c in compiled if c)
        if not toml_rules and not names:
            problems.append(f"{label} needs at least one clean_keys rule or clean_tables entry")
        if "trust_table" in table:
            trust_name = table["trust_table"]
            if not isinstance(trust_name, str) or not trust_name:
                problems.append(f"{label}.trust_table must be a non-empty string")
            else:
                trust = _compile(trust_name, f"{label}.trust_table", problems)
                if trust_name not in names:
                    problems.append(f"{label}.trust_table {trust_name!r} must appear in clean_tables")
        ordered = tuple(key for rule in toml_rules if rule.table_pattern == "" for key in rule.keys)
        filterable = set(ordered)

    record, units = table.get("picks_record"), table.get("pick_units")
    pick_units, picks_record = (), None
    if ("picks_record" in table) != ("pick_units" in table):
        problems.append(f"{label}: picks_record and pick_units must both be present or both omitted")
    elif "picks_record" in table:
        parts = record.split("/") if isinstance(record, str) else []
        if len(parts) != 2 or parts[0] != "local" or parts[1] in ("", ".", ".."):
            problems.append(f"{label}.picks_record {record!r} must be local/<filename>")
        else:
            picks_record = record
        if (not isinstance(units, list) or not units or not all(
                isinstance(u, list) and u and all(isinstance(k, str) and k for k in u) for u in units)):
            problems.append(f"{label}.pick_units must be a non-empty list of non-empty lists of "
                            "non-empty strings")
        else:
            flat = [k for u in units for k in u]
            if len(set(flat)) != len(flat):
                problems.append(f"{label}.pick_units must not repeat a key within or across units")
            pick_units = tuple(tuple(u) for u in units)
    picked = {k for u in pick_units for k in u}

    if "unrestored_keys" in table:
        unrestored = _string_list(table["unrestored_keys"], f"{label}.unrestored_keys", problems)
    else:
        unrestored = () if pick_units else tuple(k for k in ordered if k in filterable)
    unrestored = unrestored if unrestored is not None else ()
    if "picks_record" not in table and "pick_units" not in table:
        if set(unrestored) != filterable:
            problems.append(f"{label}: a clean-only entry must leave unrestored_keys unset or equal "
                            f"to the filterable keys {sorted(filterable)}")
    elif picked & set(unrestored):
        problems.append(f"{label}.unrestored_keys overlaps pick_units: {sorted(picked & set(unrestored))}")
    elif picked | set(unrestored) != filterable:
        problems.append(f"{label}: pick_units plus unrestored_keys must equal the filtered "
                        f"{'top-level ' if fmt == 'toml' else ''}keys {sorted(filterable)}, "
                        f"got {sorted(picked | set(unrestored))}")

    if len(problems) > start:
        return None
    return LiveStateSpec(name, table["config"], table["filter_glob"], filter_re, fmt, json_keys,
                         toml_rules, tables, trust, unrestored, picks_record, pick_units)


def load_manifest(path=None):
    path = Path(path) if path is not None else MANIFEST_PATH
    try:
        data = tomllib.loads(path.read_bytes().decode("utf-8"))
    except OSError as error:
        raise ManifestError(f"cannot read {path.name}: {error.strerror or error}") from None
    except UnicodeDecodeError as error:
        raise ManifestError(f"{path.name} is not valid UTF-8: {error}") from None
    except tomllib.TOMLDecodeError as error:
        raise ManifestError(f"{path.name} is not valid TOML: {error}") from None

    problems = []
    for key in sorted(set(data) - {"schema", "harnesses"}):
        problems.append(f"unknown top-level key {key!r}")
    schema = data.get("schema")
    if type(schema) is not int or schema != 1:
        problems.append(f"schema must be the integer 1, got {schema!r}")
    table = data.get("harnesses")
    if not isinstance(table, dict) or not table:
        problems.append("harnesses must be a non-empty table")
        table = {}
    names, by_harness, specs = [], {}, []
    for name, entry in table.items():
        if not SLUG.fullmatch(name):
            problems.append(f"harness name {name!r} must match [a-z][a-z0-9-]*")
            continue
        names.append(name)
        by_harness[name] = None
        if not isinstance(entry, dict):
            problems.append(f"harnesses.{name} must be a table")
            continue
        for key in sorted(set(entry) - {"live_state"}):
            problems.append(f"harnesses.{name} has unknown key {key!r}")
        if "live_state" in entry:
            spec = _parse_live_state(name, entry["live_state"], problems)
            if spec:
                by_harness[name] = spec
                specs.append(spec)

    for field in ("config", "filter_glob"):
        seen = {}
        for spec in specs:
            value = getattr(spec, field)
            if value in seen:
                problems.append(f"{field} {value!r} is used by both {seen[value]} and {spec.harness}")
            seen[value] = spec.harness
    for i, a in enumerate(specs):
        for b in specs[i + 1:]:
            if a.filter_glob != b.filter_glob and _globs_overlap(a.filter_glob, b.filter_glob):
                problems.append(f"filter_glob {a.filter_glob!r} ({a.harness}) overlaps "
                                f"{b.filter_glob!r} ({b.harness})")
    if problems:
        raise ManifestError(problems)
    return HarnessManifest(schema, tuple(names), by_harness, tuple(specs))


def load_manifest_or_exit(tool, path=None):
    try:
        return load_manifest(path)
    except ManifestError as error:
        raise SystemExit(f"{tool}: {error}") from None


def check_gitattributes(manifest, path=None):
    path = Path(path) if path is not None else GITATTRIBUTES_PATH
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise ManifestError(f"cannot read {path.name}: {error}") from None
    problems, patterns = [], []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("[attr]"):
            continue
        pattern, *attrs = line.split()
        for attr in attrs:
            name, _, value = attr.lstrip("-!").partition("=")
            if name != "filter":
                continue
            if attr == f"filter={FILTER_NAME}":
                patterns.append(pattern)
            elif attr[0] in "-!" or "harness" in value or "state" in value:
                problems.append(f".gitattributes: {pattern!r} has malformed or negated "
                                f"{attr!r}; expected filter={FILTER_NAME}")
    for pattern in sorted({p for p in patterns if patterns.count(p) > 1}):
        problems.append(f".gitattributes: {pattern!r} carries filter={FILTER_NAME} more than once")
    declared = {spec.filter_glob for spec in manifest.live_state}
    for pattern in sorted(declared - set(patterns)):
        problems.append(f".gitattributes lacks `{pattern} filter={FILTER_NAME}` declared in harnesses.toml")
    for pattern in sorted(set(patterns) - declared):
        problems.append(f".gitattributes filters {pattern!r}, which harnesses.toml does not declare")
    if problems:
        raise ManifestError(problems)


def check_filter_config(git_dir=None):
    base = ["git", f"--git-dir={git_dir}"] if git_dir is not None else ["git", "-C", str(REPO)]

    def config(*args):
        return subprocess.run([*base, "config", *args], text=True, capture_output=True)

    problems = []
    clean = config("--get", f"filter.{FILTER_NAME}.clean")
    if clean.returncode != 0 or clean.stdout.strip() != EXPECTED_CLEAN_FILTER:
        got = clean.stdout.strip() if clean.returncode == 0 else "unset"
        problems.append(f"git config filter.{FILTER_NAME}.clean is {got!r}, expected "
                        f"{EXPECTED_CLEAN_FILTER!r}; run 'just setup'")
    required = config("--bool", "--get", f"filter.{FILTER_NAME}.required")
    if required.returncode != 0 or required.stdout.strip() != "true":
        got = required.stdout.strip() if required.returncode == 0 else "unset"
        problems.append(f"git config filter.{FILTER_NAME}.required is {got!r}, expected 'true'; "
                        "run 'just setup'")
    smudge = config("--get", f"filter.{FILTER_NAME}.smudge")
    if smudge.returncode != 0 or smudge.stdout.rstrip("\n") != EXPECTED_SMUDGE_FILTER:
        got = smudge.stdout.rstrip("\n") if smudge.returncode == 0 else "unset"
        problems.append(f"git config filter.{FILTER_NAME}.smudge is {got!r}, expected "
                        f"{EXPECTED_SMUDGE_FILTER!r} (a required filter without a smudge fails "
                        "every checkout); run 'just setup'")
    if problems:
        raise ManifestError(problems)


def check_clean_tree(manifest, root=None):
    root = Path(root) if root is not None else REPO
    problems = []
    for directory, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in TREE_SKIP)
        for name in sorted(files):
            file = Path(directory) / name
            rel = file.relative_to(root).as_posix()
            spec = next((s for s in manifest.live_state if s.filter_re.fullmatch(rel)), None)
            if spec is None:
                continue
            try:
                text = file.read_bytes().decode("utf-8")
                if spec.format == "toml":
                    tomllib.loads(text)
                cleaned = clean_for_spec(spec, text)
            except (OSError, ValueError) as error:
                problems.append(f"{rel} cannot be checked ({error}); fix it, then "
                                f"`git add --renormalize {rel}`")
                continue
            if cleaned != text:
                problems.append(f"{rel} holds content the {FILTER_NAME} filter strips; "
                                f"run `git add --renormalize {rel}`")
    if problems:
        raise ManifestError(problems)


# --- Cleaners (the clean filter's mechanics) ---


def clean_json(text, keys):
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"top level is {type(data).__name__}, expected an object")
    for key in keys:
        data.pop(key, None)
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def clean_toml(text, key_rules, table_patterns):
    key_rules, table_patterns = tuple(key_rules), tuple(table_patterns)
    out = []
    table = ""
    for line in text.splitlines(keepends=True):
        header = TOML_HEADER.match(line)
        if header:
            table = header.group(1)
        if any(pattern.fullmatch(table) for pattern in table_patterns):
            continue
        key = None if header else TOML_KEY.match(line)
        if key and any(rule.table_re.fullmatch(table) and key.group(1) in rule.keys
                       for rule in key_rules):
            continue
        out.append(line)
    return "".join(out)


def clean_for_spec(spec, text):
    if spec.format == "json":
        return clean_json(text, spec.json_clean_keys)
    return clean_toml(text, spec.toml_clean_keys, spec.toml_clean_tables)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="harness_state.py")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="validate harnesses.toml, .gitattributes and filter config")
    check.add_argument("--git-dir", type=Path)
    check.add_argument("--staged-tree", action="store_true")
    args = parser.parse_args(argv)
    problems = []
    try:
        manifest = load_manifest(MANIFEST_PATH)
    except ManifestError as error:
        problems += error.problems
        manifest = None
    steps = [lambda: check_filter_config(args.git_dir)]
    if manifest:
        steps += [lambda: check_gitattributes(manifest, GITATTRIBUTES_PATH)]
        if args.staged_tree:
            steps += [lambda: check_clean_tree(manifest, REPO)]
    for step in steps:
        try:
            step()
        except ManifestError as error:
            problems += error.problems
    for problem in problems:
        print(f"harness-state: {problem}", file=sys.stderr)
    return 2 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
