"""Fixture helpers for the relocated per-file readers."""
from pathlib import Path
import shutil

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "session-logs"

PATHS = {
    "CA": "home/.claude/projects/-w-alpha/c0000000-0000-4000-8000-00000000000a.jsonl",
    "AG": "home/.claude/projects/-w-alpha/c0000000-0000-4000-8000-00000000000a/subagents/agent-a0000000000000b01.jsonl",
    "CW": "home/.claude-work/projects/-w-beta/c0000000-0000-4000-8000-00000000000b.jsonl",
    "CW2": "home/.claude-work/projects/-w-beta/c0000000-0000-4000-8000-00000000000c.jsonl",
    "XP": "home/.codex/sessions/2026/10/08/rollout-2026-10-08T10-00-00-01900000-0000-7000-8000-0000000000a1.jsonl",
    "XC": "home/.codex/sessions/2026/10/08/rollout-2026-10-08T10-00-11-01900000-0000-7000-8000-0000000000c1.jsonl",
    "XG": "home/.codex/sessions/2026/10/08/rollout-2026-10-08T10-00-32-01900000-0000-7000-8000-0000000000c2.jsonl",
    "XA": "home/.codex/archived_sessions/rollout-2026-09-20T09-00-00-01900000-0000-7000-8000-0000000000a2.jsonl",
    "XW": "home/.codex-work/sessions/2026/10/10/rollout-2026-10-10T08-00-00-01900000-0000-7000-8000-0000000000b1.jsonl",
    "CD": "degraded/.claude/projects/-w-delta/c0000000-0000-4000-8000-00000000000d.jsonl",
    "CU": "degraded/.claude-work/projects/-w-delta/c0000000-0000-4000-8000-00000000000e.jsonl",
    "XD": "degraded/.codex/sessions/2026/10/11/rollout-2026-10-11T10-00-00-01900000-0000-7000-8000-0000000000d1.jsonl",
    "CM": "turns/.claude/projects/-w-gamma/c0000000-0000-4000-8000-000000000021.jsonl",
    "CT1": "turns/.claude/projects/-w-gamma/c0000000-0000-4000-8000-000000000022.jsonl",
    "CT2": "turns/.claude/projects/-w-gamma/c0000000-0000-4000-8000-000000000023.jsonl",
    "CT3": "turns/.claude/projects/-w-gamma/c0000000-0000-4000-8000-000000000024.jsonl",
    "XE": "turns/.codex/sessions/2026/10/12/rollout-2026-10-12T10-00-00-01900000-0000-7000-8000-0000000000e1.jsonl",
    "XF": "turns/.codex/sessions/2026/10/12/rollout-2026-10-12T10-05-00-01900000-0000-7000-8000-0000000000f1.jsonl",
    "XK": "turns/.codex/sessions/2026/10/12/rollout-2026-10-12T11-00-00-01900000-0000-7000-8000-0000000000f2.jsonl",
}


CAPTURES = {
    "SDK": "captures/sdk-stream.jsonl",
    "ESC": "captures/escaped.jsonl",
    "ESM": "captures/escaped-malformed.jsonl",
}


def path_of(short: str) -> str:
    """The fixture-relative path of a short name (store files and captures)."""
    return PATHS[short] if short in PATHS else CAPTURES[short]


def ref_of(short: str, given: str | None = None) -> str:
    """Acceptance notation ("CA:4#0", "XC:1", "SDK:4") to the reader's ref.

    A store file becomes `<home>:<path under the home directory>#L<n>[#<block>]`, with home
    the dot-directory's name without its dot. A capture (SDK, ESC, ESM) is an
    explicit file, so its ref is `file:<given>#L<n>`: `given` is the path exactly as the
    test passes it to the reader, required for captures and refused for store files."""
    name, _, rest = short.partition(":")
    if not rest:
        raise ValueError(f"{short!r} has no line number")
    line, _, block = rest.partition("#")
    suffix = f"#L{line}" + (f"#{block}" if block else "")
    if name in CAPTURES:
        if given is None:
            raise ValueError(f"{name} is an explicit file: pass given=<path as given>")
        return f"file:{given}{suffix}"
    if given is not None:
        raise ValueError(f"{name} is a store file: given applies to captures")
    _fixture, dot, under = PATHS[name].split("/", 2)
    return f"{dot[1:]}:{under}{suffix}"


def materialize(name: str, dest: Path) -> Path:
    """Copy fixture home `name` (home, degraded or turns) under dest and return the copy.
    For degraded, CU is made unreadable, as git cannot store that."""
    home = Path(dest) / name
    shutil.copytree(FIXTURES / name, home)
    if name == "degraded":
        (home / path_of("CU").split("/", 1)[1]).chmod(0)
    return home


def no_parent(_inherited_id):
    raise AssertionError("an unforked rollout never looks up an inherited thread")
