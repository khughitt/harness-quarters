"""`hq sessions` over synthetic homes under a temp HOME, launching stub `claude`/`codex`
executables that print their argv, cwd and both home variables as JSON."""
import json
import os
import pty
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parent / "hq"
SID = "aaaaaaaa-1111-4111-8111-000000000001"
SID2 = "bbbbbbbb-2222-4222-8222-000000000002"
TID = "019e0000-0000-7000-8000-00000000000a"
TID2 = "019e1111-0000-7000-8000-00000000000b"
TID3 = "019e2222-0000-7000-8000-00000000000c"
NOW_MS = int(time.time() * 1000)
CODEX_COLUMNS = ("id", "rollout_path", "source", "thread_source", "archived", "preview", "cwd",
                 "recency_at_ms", "name", "title")

STUB = """#!{python}
import json, os, sys
print(json.dumps({{"tool": {tool!r}, "argv": sys.argv[1:], "cwd": os.getcwd(),
                  "CLAUDE_CONFIG_DIR": os.environ.get("CLAUDE_CONFIG_DIR"),
                  "CODEX_HOME": os.environ.get("CODEX_HOME")}}))
"""

# `tasks resolve --stdin` over the project roots in $TASKS_STUB_ROOTS ({"prefix": root});
# a path under <root>/.worktrees/<name> is that worktree. A path containing a word from
# $TASKS_STUB_STATUS ({"word": "ambiguous" | "invalid"}) gets that status; $TASKS_STUB_FAIL
# makes the command fail; each call appends its input to $TASKS_STUB_LOG.
TASKS_STUB = """#!{python}
import json, os, sys
if sys.argv[1:] != ["resolve", "--stdin"]:
    sys.exit("unexpected arguments: " + " ".join(sys.argv[1:]))
if os.environ.get("TASKS_STUB_FAIL"):
    print('{{"error":{{"kind":"registry","detail":"broken registry"}}}}', file=sys.stderr)
    sys.exit(1)
paths = sys.stdin.read().splitlines()
if os.environ.get("TASKS_STUB_LOG"):
    with open(os.environ["TASKS_STUB_LOG"], "a") as log:
        log.write(json.dumps(paths) + "\\n")
roots = json.loads(os.environ.get("TASKS_STUB_ROOTS", "{{}}"))
forced = json.loads(os.environ.get("TASKS_STUB_STATUS", "{{}}"))
results = []
for path in paths:
    row = {{"input": path, "kind": "path", "status": "unregistered"}}
    for word, status in forced.items():
        if word in path:
            row["status"] = status
    for prefix, root in roots.items():
        if row["status"] == "unregistered" and (path == root or path.startswith(root + "/")):
            rest = path[len(root):].strip("/")
            row.update(status="resolved", prefix=prefix, root=root, via="root", location=root, relpath=rest)
            parts = rest.split("/")
            if parts == [".worktrees"]:
                row.update(via="storage", location=root + "/.worktrees", relpath="")
            if len(parts) >= 2 and parts[0] == ".worktrees":
                row.update(via="storage", location=root + "/.worktrees",
                           worktree=root + "/.worktrees/" + parts[1], relpath="/".join(parts[2:]))
    results.append(row)
print(json.dumps({{"results": results, "warnings": []}}))
"""

# Picks the input line whose leading number is $FZF_PICK, after deleting $FZF_DELETE
# (a transcript that disappears between listing and launch).
FZF_STUB = """#!{python}
import os, sys
lines = sys.stdin.read().splitlines()
if os.environ.get("FZF_DELETE"):
    os.remove(os.environ["FZF_DELETE"])
pick = os.environ.get("FZF_PICK")
if not pick:
    sys.exit(130)
print(next(line for line in lines if line.split("\\t")[0] == pick))
"""


class Env:
    def __init__(self, tmp_path: Path):
        self.root = tmp_path
        self.home = tmp_path / "home"
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        for name in (".claude", ".claude-work", ".codex", ".codex-work"):
            (self.home / name).mkdir(parents=True)
        for name in (".claude", ".claude-work"):
            (self.home / name / "history.jsonl").write_text("")
        for name in (".codex", ".codex-work"):
            codex_db(self.home / name, [])
        for tool in ("claude", "codex"):
            self.script(tool, STUB.format(python=sys.executable, tool=tool))
        self.script("tasks", TASKS_STUB.format(python=sys.executable))
        (self.bin / "git").symlink_to(shutil.which("git"))
        self.extra: dict[str, str] = {}

    def script(self, name: str, text: str) -> None:
        path = self.bin / name
        path.write_text(text)
        path.chmod(0o755)

    def project(self, name: str) -> Path:
        path = self.root / "work" / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def run(self, *args: str, input: str | None = None, cwd: Path | None = None,
            **extra: str) -> subprocess.CompletedProcess:
        env = {"HOME": str(self.home), "PATH": str(self.bin), **self.extra, **extra}
        return subprocess.run([sys.executable, str(TOOL), *args], env=env, input=input,
                              capture_output=True, text=True, cwd=cwd or self.root)


@pytest.fixture
def env(tmp_path):
    return Env(tmp_path)


def history(home: Path, *lines) -> None:
    with (home / "history.jsonl").open("a") as handle:
        for line in lines:
            handle.write((line if isinstance(line, str) else json.dumps(line, ensure_ascii=False)) + "\n")


def prompt(sid: str | None, project: Path, display: str, timestamp: int = NOW_MS) -> dict:
    row = {"display": display, "pastedContents": {}, "timestamp": timestamp, "project": str(project)}
    if sid is not None:
        row["sessionId"] = sid
    return row


def transcript(home: Path, sid: str, age_s: float = 0, directory: str = "-p") -> Path:
    path = home / "projects" / directory / f"{sid}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"type":"user"}\n')
    stamp = time.time() - age_s
    os.utime(path, (stamp, stamp))
    return path


def claude_session(home: Path, sid: str, project: Path, display: str = "hello there",
                   age_s: float = 0) -> Path:
    history(home, prompt(sid, project, display))
    return transcript(home, sid, age_s)


def codex_db(home: Path, rows: list[dict], drop: str | None = None) -> None:
    columns = [c for c in CODEX_COLUMNS if c != drop]
    path = home / "state_5.sqlite"
    path.unlink(missing_ok=True)
    with sqlite3.connect(path) as db:
        db.execute(f"CREATE TABLE threads ({', '.join(columns)})")
        for row in rows:
            db.execute(f"INSERT INTO threads ({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))})",
                       [row.get(c) for c in columns])
    db.close()


def thread(home: Path, tid: str, cwd: Path, age_s: float = 0, rollout: bool = True, **fields) -> dict:
    path = home / "sessions" / f"rollout-{tid}.jsonl"
    if rollout:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n")
    return {"id": tid, "rollout_path": str(path), "source": "cli", "thread_source": "user",
            "archived": 0, "preview": "a prompt", "cwd": str(cwd),
            "recency_at_ms": int(time.time() * 1000) - int(age_s * 1000), "name": None, "title": "a title", **fields}


def rows(result: subprocess.CompletedProcess) -> list[str]:
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    return [line for line in lines[:-1] if line.strip()]


def footer(result: subprocess.CompletedProcess) -> str:
    assert result.returncode == 0, result.stderr
    return result.stdout.splitlines()[-1]


def launched(result: subprocess.CompletedProcess) -> dict:
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.splitlines()[-1])


# --- listing --------------------------------------------------------------------------


def test_claude_row_shows_harness_home_id_cwd_and_first_prompt(env):
    project = env.project("alpha")
    history(env.home / ".claude", prompt(SID, project, "first   prompt\nline two"),
            prompt(SID, project, "second prompt"))
    transcript(env.home / ".claude", SID)
    [row] = rows(env.run("sessions"))
    assert row.split()[:3] == ["claude", "personal", SID[:8]]
    assert str(project) in row
    assert "first prompt line two" in row
    assert "second prompt" not in row


def test_claude_transcript_found_under_any_project_directory(env):
    project = env.project("alpha")
    history(env.home / ".claude", prompt(SID, project, "hi"))
    transcript(env.home / ".claude", SID, directory="-somewhere-else")
    assert len(rows(env.run("sessions"))) == 1


def test_claude_work_row(env):
    claude_session(env.home / ".claude-work", SID, env.project("alpha"))
    [row] = rows(env.run("sessions"))
    assert row.split()[:2] == ["claude", "work"]


def test_codex_rows_label_with_name_else_title(env):
    project = env.project("beta")
    codex_db(env.home / ".codex", [thread(env.home / ".codex", TID, project, name="Named thread"),
                                   thread(env.home / ".codex", TID2, project, age_s=60, title="Titled  thread")])
    first, second = rows(env.run("sessions"))
    assert first.split()[:3] == ["codex", "personal", TID[:8]]
    assert "Named thread" in first and "a title" not in first
    assert "Titled thread" in second


def test_codex_work_row(env):
    codex_db(env.home / ".codex-work", [thread(env.home / ".codex-work", TID, env.project("beta"))])
    [row] = rows(env.run("sessions"))
    assert row.split()[:2] == ["codex", "work"]


def test_cwd_under_home_is_shortened(env):
    project = env.home / "src" / "gamma"
    project.mkdir(parents=True)
    claude_session(env.home / ".claude", SID, project)
    [row] = rows(env.run("sessions"))
    assert "~/src/gamma" in row and str(env.home) not in row


def test_newest_first_by_transcript_mtime_and_codex_recency(env):
    project = env.project("alpha")
    # The Claude history timestamp says newest; its transcript mtime (the recency used) says oldest.
    history(env.home / ".claude", prompt(SID, project, "claude old", timestamp=NOW_MS + 10_000))
    transcript(env.home / ".claude", SID, age_s=3600)
    claude_session(env.home / ".claude-work", SID2, project, display="claude new", age_s=0)
    codex_db(env.home / ".codex", [thread(env.home / ".codex", TID, project, age_s=60, name="codex mid")])
    labels = [row.split()[-1] for row in rows(env.run("sessions"))]
    assert labels == ["new", "mid", "old"]


def test_claude_recency_falls_back_to_history_timestamp_when_stat_fails(tmp_path):
    sys.path.insert(0, str(TOOL.parent))
    from hq_cli import sessions
    assert sessions.claude_recency_ms(tmp_path / "gone.jsonl", 1234) == 1234
    present = tmp_path / "here.jsonl"
    present.write_text("")
    os.utime(present, (100, 100))
    assert sessions.claude_recency_ms(present, 1234) == 100_000


def test_default_limit_is_20_and_n_changes_it(env):
    project = env.project("alpha")
    codex_db(env.home / ".codex", [thread(env.home / ".codex", f"019e0000-0000-7000-8000-{i:012d}", project,
                                          age_s=i) for i in range(25)])
    result = env.run("sessions")
    assert len(rows(result)) == 20
    assert footer(result).startswith("20 of 25 shown")
    assert len(rows(env.run("sessions", "-n", "3"))) == 3


def test_missing_cwd_is_listed_and_marked(env):
    gone = env.root / "removed-worktree"
    claude_session(env.home / ".claude", SID, gone)
    [row] = rows(env.run("sessions"))
    assert "cwd missing" in row


def test_long_label_is_trimmed(env):
    claude_session(env.home / ".claude", SID, env.project("alpha"), display="x" * 200)
    [row] = rows(env.run("sessions"))
    assert "x" * 61 not in row and "x" * 50 in row


# --- project names ----------------------------------------------------------------------


def projects(env, **roots: Path) -> None:
    env.extra["TASKS_STUB_ROOTS"] = json.dumps({prefix: str(root) for prefix, root in roots.items()})


def place(row: str) -> str:
    """The place column: the fifth whitespace-separated field."""
    return row.split()[4]


def test_cwd_in_a_project_shows_its_prefix(env):
    alpha = env.project("alpha")
    claude_session(env.home / ".claude", SID, alpha)
    projects(env, al=alpha)
    [row] = rows(env.run("sessions"))
    assert place(row) == "al" and str(alpha) not in row


def test_cwd_below_a_project_root_shows_the_relative_path(env):
    alpha = env.project("alpha")
    (alpha / "sub" / "dir").mkdir(parents=True)
    claude_session(env.home / ".claude", SID, alpha / "sub" / "dir")
    projects(env, al=alpha)
    [row] = rows(env.run("sessions"))
    assert place(row) == "al/sub/dir"


def test_cwd_in_a_worktree_shows_prefix_at_worktree(env):
    alpha = env.project("alpha")
    (alpha / ".worktrees" / "feature" / "src").mkdir(parents=True)
    claude_session(env.home / ".claude", SID, alpha / ".worktrees" / "feature", display="top")
    codex_db(env.home / ".codex", [thread(env.home / ".codex", TID, alpha / ".worktrees" / "feature" / "src",
                                          age_s=60, name="below")])
    projects(env, al=alpha)
    result = env.run("sessions")
    assert {row.split()[-1]: place(row) for row in rows(result)} == {"top": "al@feature", "below": "al@feature/src"}


def test_removed_worktree_keeps_its_name_and_is_marked_missing(env):
    alpha = env.project("alpha")
    claude_session(env.home / ".claude", SID, alpha / ".worktrees" / "gone")
    projects(env, al=alpha)
    [row] = rows(env.run("sessions"))
    assert "al@gone (cwd missing)" in row


def test_cwd_outside_every_project_keeps_its_path(env):
    alpha, beta = env.project("alpha"), env.home / "src" / "beta"
    beta.mkdir(parents=True)
    claude_session(env.home / ".claude", SID, beta)
    projects(env, al=alpha)
    result = env.run("sessions")
    [row] = rows(result)
    assert place(row) == "~/src/beta" and "unresolved" not in footer(result)


def test_worktree_storage_directory_is_named_as_such(env):
    alpha = env.project("alpha")
    (alpha / ".worktrees").mkdir()
    claude_session(env.home / ".claude", SID, alpha / ".worktrees")
    projects(env, al=alpha)
    [row] = rows(env.run("sessions"))
    assert place(row) == "al/.worktrees"


def test_ambiguous_cwd_keeps_its_path(env):
    alpha = env.project("alpha")
    claude_session(env.home / ".claude", SID, alpha)
    projects(env, al=alpha)
    env.extra["TASKS_STUB_STATUS"] = json.dumps({"alpha": "ambiguous"})
    result = env.run("sessions")
    [row] = rows(result)
    assert place(row) == str(alpha) and "unresolved" not in footer(result)


def test_invalid_path_keeps_its_path_and_is_counted(env):
    """tasks answers `invalid` for one path it cannot read (permission, a stale mount);
    that row keeps its path and the footer counts it, and the rest still list."""
    alpha, beta = env.project("alpha"), env.project("beta")
    claude_session(env.home / ".claude", SID, alpha)
    claude_session(env.home / ".claude", SID2, beta, age_s=60)
    projects(env, al=alpha, be=beta)
    env.extra["TASKS_STUB_STATUS"] = json.dumps({"/alpha": "invalid"})
    result = env.run("sessions")
    assert [place(row) for row in rows(result)] == [str(alpha), "be"]
    assert "unresolved cwds: 1" in footer(result)
    assert "unresolved" not in footer(env.run("sessions", "-n", "1", "--home", "work"))


def test_source_text_cannot_carry_terminal_escapes_or_surrogates(env):
    """A prompt holding an escape sequence or a session id holding a lone surrogate prints
    with `?` in their place, so neither reaches the terminal or breaks a UTF-8 stream."""
    alpha = env.project("alpha")
    history(env.home / ".claude", '{"display": "red \\u001b[31m text", "timestamp": %d, "project": "%s",'
            ' "sessionId": "ab\\udcffcdefgh"}' % (NOW_MS, alpha))
    transcript(env.home / ".claude", "ab\udcffcdefgh")
    result = env.run("sessions", "--color", "never", PYTHONIOENCODING="utf-8")
    [row] = rows(result)
    assert "\x1b" not in result.stdout
    assert row.split()[2] == "ab?cdefg" and row.endswith("red ?[31m text")


def test_resolved_worktree_and_relpath_cannot_carry_controls(env):
    """A directory name under a project reaches the place column through tasks' answer."""
    alpha = env.project("alpha")
    claude_session(env.home / ".claude", SID, alpha / ".worktrees" / "w\x1b]0;t\x07" / "a\tb\u009b2J")
    projects(env, al=alpha)
    result = env.run("sessions", "--color", "always", PYTHONIOENCODING="utf-8")
    [row] = rows(result)
    assert strip(row).split()[4] == "al@w?]0;t?/a?b?2J"
    assert "\x07" not in result.stdout and "\t" not in result.stdout and "\u009b" not in result.stdout


def test_label_c1_controls_print_as_replacements(env):
    claude_session(env.home / ".claude", SID, env.project("alpha"), display="clear \u009b2J \u009d0;x")
    [row] = rows(env.run("sessions", PYTHONIOENCODING="utf-8"))
    assert row.endswith("clear ?2J ?0;x")


def test_unresolved_cwds_count_once_each_across_causes(env):
    """Two rows in one unreadable cwd count once; an unsendable cwd adds one more."""
    alpha, beta = env.project("alpha"), env.project("beta")
    claude_session(env.home / ".claude", SID, alpha)
    claude_session(env.home / ".claude-work", SID2, alpha, age_s=60)
    history(env.home / ".claude", '{"display": "odd", "timestamp": %d, "project": "%s/x\\udcff", "sessionId": "%s"}'
            % (NOW_MS, beta, "cccccccc-3333-4333-8333-000000000003"))
    transcript(env.home / ".claude", "cccccccc-3333-4333-8333-000000000003", age_s=120)
    projects(env, al=alpha, be=beta)
    env.extra["TASKS_STUB_STATUS"] = json.dumps({"/alpha": "invalid"})
    result = env.run("sessions", PYTHONIOENCODING="utf-8")
    assert len(rows(result)) == 3
    assert "unresolved cwds: 2" in footer(result)


def test_cwd_with_a_line_break_keeps_its_path_and_is_counted(env):
    """One stdin line per cwd: a line break would split it, so it is not sent."""
    alpha = env.project("alpha")
    history(env.home / ".claude", prompt(SID, alpha / "a\nb", "newline"),
            prompt(SID2, alpha / "c\rd", "return"))
    transcript(env.home / ".claude", SID)
    transcript(env.home / ".claude", SID2)
    projects(env, al=alpha)
    result = env.run("sessions")
    assert len(rows(result)) == 2 and "Traceback" not in result.stderr
    assert "unresolved cwds: 2" in footer(result)
    assert "al/" not in result.stdout


def test_storage_row_with_a_relpath_is_an_error(env):
    """The contract leaves relpath empty when a storage match names no worktree."""
    sys.path.insert(0, str(TOOL.parent))
    from hq_cli import projects as hq_projects
    row = {"prefix": "hq", "via": "storage", "location": "/x/.worktrees", "relpath": "y"}
    with pytest.raises(hq_projects.ProjectError):
        hq_projects.place(row)
    assert hq_projects.place({**row, "relpath": ""}) == hq_projects.Place("hq", None, ".worktrees")


def test_unknown_resolve_status_is_an_error(env):
    claude_session(env.home / ".claude", SID, env.project("alpha"))
    env.extra["TASKS_STUB_STATUS"] = json.dumps({"/alpha": "surprising"})
    result = env.run("sessions")
    assert result.returncode != 0
    assert "tasks resolve" in result.stderr and "surprising" in result.stderr
    assert "Traceback" not in result.stderr


def test_lone_surrogates_print_as_replacements_and_the_cwd_is_counted(env):
    """A \\udcXX escape in a history line decodes to a lone surrogate, which no UTF-8
    stream can carry: the cwd is not sent to tasks, and both columns print `?` for it."""
    alpha = env.project("alpha")
    history(env.home / ".claude", '{"display": "odd \\udcff prompt", "timestamp": %d, "project": "%s/x\\udcff",'
            ' "sessionId": "%s"}' % (NOW_MS, alpha, SID))
    transcript(env.home / ".claude", SID)
    projects(env, al=alpha)
    result = env.run("sessions", PYTHONIOENCODING="utf-8")
    [row] = rows(result)
    assert f"{alpha}/x? (cwd missing)" in row and row.endswith("odd ? prompt")
    assert "unresolved cwds: 1" in footer(result)


def test_failing_tasks_resolve_is_an_error(env):
    claude_session(env.home / ".claude", SID, env.project("alpha"))
    result = env.run("sessions", TASKS_STUB_FAIL="1")
    assert result.returncode != 0
    assert "tasks resolve" in result.stderr and "broken registry" in result.stderr
    assert "Traceback" not in result.stderr


def test_missing_tasks_cli_is_an_error(env):
    claude_session(env.home / ".claude", SID, env.project("alpha"))
    (env.bin / "tasks").unlink()
    result = env.run("sessions")
    assert result.returncode != 0
    assert "tasks" in result.stderr and "PATH" in result.stderr
    assert "Traceback" not in result.stderr


def test_one_resolve_call_for_the_shown_rows_only(env, tmp_path):
    alpha, beta = env.project("alpha"), env.project("beta")
    for n in range(4):
        history(env.home / ".claude", prompt(f"aaaaaaaa-1111-4111-8111-00000000000{n}", alpha if n % 2 else beta, "x"))
        transcript(env.home / ".claude", f"aaaaaaaa-1111-4111-8111-00000000000{n}", age_s=n * 60)
    log = tmp_path / "resolve.log"
    rows(env.run("sessions", "-n", "1", TASKS_STUB_LOG=str(log)))
    assert [json.loads(line) for line in log.read_text().splitlines()] == [[str(beta)]]


def test_no_rows_needs_no_resolve(env):
    (env.bin / "tasks").unlink()
    assert rows(env.run("sessions")) == []


def test_launch_uses_the_cwd_not_the_project_name(env):
    alpha = env.project("alpha")
    claude_session(env.home / ".claude", SID, alpha)
    projects(env, al=alpha)
    assert launched(env.run("sessions", "-i", input="1\n"))["cwd"] == str(alpha)


# --- visibility and filters -------------------------------------------------------------


def populate_all(env) -> dict[str, Path]:
    alpha, beta = env.project("alpha"), env.project("beta")
    claude_session(env.home / ".claude", SID, alpha, display="claude-personal")
    claude_session(env.home / ".claude-work", SID2, beta, display="claude-work")
    codex_db(env.home / ".codex", [thread(env.home / ".codex", TID, alpha, name="codex-personal"),
                                   thread(env.home / ".codex", TID2, alpha, name="codex-archived", archived=1)])
    codex_db(env.home / ".codex-work", [thread(env.home / ".codex-work", TID3, beta, name="codex-work")])
    return {"alpha": alpha, "beta": beta}


def labels(result) -> set[str]:
    return {row.split()[-1] for row in rows(result)}


def test_default_shows_every_home_and_hides_archived(env):
    populate_all(env)
    assert labels(env.run("sessions")) == {"claude-personal", "claude-work", "codex-personal", "codex-work"}


def test_filter_harness(env):
    populate_all(env)
    assert labels(env.run("sessions", "--harness", "claude")) == {"claude-personal", "claude-work"}
    assert labels(env.run("sessions", "--harness", "codex")) == {"codex-personal", "codex-work"}


def test_filter_home(env):
    populate_all(env)
    assert labels(env.run("sessions", "--home", "work")) == {"claude-work", "codex-work"}
    assert labels(env.run("sessions", "--home", "personal")) == {"claude-personal", "codex-personal"}


def test_archived_flag_shows_archived_codex_threads(env):
    populate_all(env)
    assert "codex-archived" in labels(env.run("sessions", "--archived"))


def test_empty_preview_codex_rows_stay_hidden_and_uncounted(env):
    project = env.project("alpha")
    codex_db(env.home / ".codex", [
        thread(env.home / ".codex", TID, project, preview=""),
        thread(env.home / ".codex", TID2, project, preview="", source="exec"),
        thread(env.home / ".codex", TID3, project, preview="", rollout=False),
    ])
    result = env.run("sessions", "--archived")
    assert rows(result) == []
    assert "codex 0 non-interactive, 0 transcript gone" in footer(result)


def test_archived_codex_rows_are_counted_only_with_archived(env):
    project = env.project("alpha")
    codex_db(env.home / ".codex", [thread(env.home / ".codex", TID, project, archived=1, source="exec"),
                                   thread(env.home / ".codex", TID2, project, archived=1, rollout=False)])
    assert "codex 0 non-interactive, 0 transcript gone" in footer(env.run("sessions"))
    assert "codex 1 non-interactive, 1 transcript gone" in footer(env.run("sessions", "--archived"))


def test_here_keeps_sessions_inside_the_checkout_and_its_worktrees(env):
    checkout = env.project("repo")
    git = ["git", "-C", str(checkout)]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty",
                    "-m", "init"], check=True)
    linked = env.root / "elsewhere" / "wt"
    subprocess.run([*git, "worktree", "add", "-q", str(linked)], check=True)
    sub = checkout / "sub"
    sub.mkdir()
    claude_session(env.home / ".claude", SID, sub, display="in-checkout")
    codex_db(env.home / ".codex", [thread(env.home / ".codex", TID, linked, name="in-worktree"),
                                   thread(env.home / ".codex", TID2, env.project("other"), name="outside")])
    assert labels(env.run("sessions", "--here", cwd=sub)) == {"in-checkout", "in-worktree"}
    assert labels(env.run("sessions", "--here", cwd=linked)) == {"in-checkout", "in-worktree"}
    assert labels(env.run("sessions")) == {"in-checkout", "in-worktree", "outside"}


def test_here_follows_symlinks_and_removed_worktrees_and_skips_siblings(env):
    storage = env.root / "storage" / ".worktrees"
    storage.mkdir(parents=True)
    checkout = env.project("repo")
    git = ["git", "-C", str(checkout)]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty",
                    "-m", "init"], check=True)
    (checkout / ".worktrees").symlink_to(storage)
    alias = env.root / "alias"
    alias.symlink_to(checkout)
    sibling = env.project("repo2")
    codex_db(env.home / ".codex", [
        thread(env.home / ".codex", "019e0000-0000-7000-8000-0000000000c1", alias, name="via-alias"),
        thread(env.home / ".codex", "019e0000-0000-7000-8000-0000000000c2", storage / "gone", name="removed-real"),
        thread(env.home / ".codex", "019e0000-0000-7000-8000-0000000000c3", alias / ".worktrees" / "gone2",
               name="removed-via-alias"),
        thread(env.home / ".codex", "019e0000-0000-7000-8000-0000000000c4", sibling, name="sibling"),
        thread(env.home / ".codex", "019e0000-0000-7000-8000-0000000000c5", Path(f"{checkout}/../repo2"),
               name="dotdot-sibling"),
    ])
    assert labels(env.run("sessions", "--here", cwd=checkout)) == {"via-alias", "removed-real",
                                                                    "removed-via-alias"}


def test_here_outside_a_checkout_is_an_error(env):
    result = env.run("sessions", "--here")
    assert result.returncode != 0
    assert "--here" in result.stderr


# --- footer -------------------------------------------------------------------------------


def test_footer_counts_skipped_history_lines_apart_from_excluded_sessions(env):
    project = env.project("alpha")
    claude_session(env.home / ".claude", SID, project)
    history(env.home / ".claude", prompt(None, project, "old line"), prompt(None, project, "older"),
            "{not json", '["a list"]')
    history(env.home / ".claude-work", prompt(SID2, project, "pruned"))   # no transcript
    codex_db(env.home / ".codex", [
        thread(env.home / ".codex", TID, project),
        thread(env.home / ".codex", "019e0000-0000-7000-8000-0000000000e1", project, source="exec"),
        thread(env.home / ".codex", "019e0000-0000-7000-8000-0000000000e2", project,
               source='{"subagent":"review"}', thread_source="subagent"),
        thread(env.home / ".codex", "019e0000-0000-7000-8000-0000000000e3", project, thread_source="subagent"),
        thread(env.home / ".codex", "019e0000-0000-7000-8000-0000000000e4", project, source="vscode",
               thread_source=None),
        thread(env.home / ".codex", "019e0000-0000-7000-8000-0000000000e5", project, rollout=False),
    ])
    result = env.run("sessions")
    assert len(rows(result)) == 3
    line = footer(result)
    assert "skipped claude history lines: 2 without sessionId, 2 malformed" in line
    assert "excluded: claude 1 transcript gone; codex 3 non-interactive, 1 transcript gone" in line
    assert "subagent" not in line and "SDK" not in line


def test_footer_counts_only_selected_harness(env):
    populate_all(env)
    line = footer(env.run("sessions", "--harness", "codex"))
    assert "claude" not in line
    assert "codex 0 non-interactive, 0 transcript gone" in line


def test_absent_home_is_named_not_an_error(env):
    shutil.rmtree(env.home / ".codex-work")
    result = env.run("sessions")
    assert "absent: codex-work" in footer(result)


def test_line_separator_inside_a_prompt_keeps_the_line_whole(env):
    claude_session(env.home / ".claude", SID, env.project("alpha"), display="before\u2028after")
    result = env.run("sessions")
    assert len(rows(result)) == 1
    assert "0 without sessionId, 0 malformed" in footer(result)


def test_claude_relative_project_is_a_malformed_line(env):
    history(env.home / ".claude", {"display": "x", "timestamp": NOW_MS, "project": "rel/dir", "sessionId": SID})
    transcript(env.home / ".claude", SID)
    result = env.run("sessions")
    assert rows(result) == []
    assert "0 without sessionId, 1 malformed" in footer(result)


def test_codex_rollout_that_is_a_directory_counts_as_gone(env):
    row = thread(env.home / ".codex", TID, env.project("beta"), rollout=False)
    Path(row["rollout_path"]).mkdir(parents=True)
    codex_db(env.home / ".codex", [row])
    assert "codex 0 non-interactive, 1 transcript gone" in footer(env.run("sessions"))


def test_listing_survives_a_closed_pipe(env):
    project = env.project("alpha")
    codex_db(env.home / ".codex", [thread(env.home / ".codex", f"019e0000-0000-7000-8000-{i:012d}", project,
                                          age_s=i, title="t" * 50) for i in range(3000)])
    proc = subprocess.Popen([sys.executable, str(TOOL), "sessions", "-n", "3000"], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env={"HOME": str(env.home), "PATH": str(env.bin)})
    proc.stdout.readline()
    proc.stdout.close()
    stderr = proc.stderr.read().decode()
    proc.wait()
    assert "Traceback" not in stderr


def run_closed(env, *args: str, input: str | None = None) -> subprocess.CompletedProcess:
    """Run with stdout a pipe whose reader closed before anything was written."""
    read, write = os.pipe()
    os.close(read)
    try:
        return subprocess.run([sys.executable, str(TOOL), *args], stdout=write, stderr=subprocess.PIPE,
                              input=input, text=True, env={"HOME": str(env.home), "PATH": str(env.bin)})
    finally:
        os.close(write)


def test_short_listing_into_a_closed_pipe_exits_quietly(env):
    claude_session(env.home / ".claude", SID, env.project("alpha"))
    result = run_closed(env, "sessions")
    assert result.returncode == 0 and result.stderr == ""


def test_pick_into_a_closed_pipe_fails_and_says_nothing_launched(env):
    claude_session(env.home / ".claude", SID, env.project("alpha"))
    result = run_closed(env, "sessions", "-i", input="1\n")
    assert result.returncode == 1
    assert "nothing launched" in result.stderr


# --- fail early ---------------------------------------------------------------------------


def test_missing_codex_state_db_is_an_error_naming_the_file(env):
    (env.home / ".codex" / "state_5.sqlite").unlink()
    result = env.run("sessions")
    assert result.returncode != 0
    assert str(env.home / ".codex" / "state_5.sqlite") in result.stderr


@pytest.mark.parametrize("column", ["recency_at_ms", "thread_source", "rollout_path"])
def test_codex_schema_drift_is_an_error_naming_the_file(env, column):
    codex_db(env.home / ".codex", [], drop=column)
    result = env.run("sessions")
    assert result.returncode != 0
    assert str(env.home / ".codex" / "state_5.sqlite") in result.stderr
    assert column in result.stderr


@pytest.mark.parametrize("field,value", [("cwd", None), ("cwd", "relative/dir"), ("rollout_path", None),
                                         ("rollout_path", "sessions/r.jsonl"), ("recency_at_ms", "soon"),
                                         ("id", None), ("source", None)])
def test_codex_unexpected_value_is_an_error_naming_the_file(env, field, value):
    row = thread(env.home / ".codex", TID, env.project("beta"))
    codex_db(env.home / ".codex", [{**row, field: value}])
    result = env.run("sessions")
    assert result.returncode != 0
    assert str(env.home / ".codex" / "state_5.sqlite") in result.stderr and field in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("value", [None, 2, "1"])
def test_codex_unexpected_archived_value_is_an_error_under_archived(env, value):
    row = thread(env.home / ".codex", TID, env.project("beta"))
    codex_db(env.home / ".codex", [{**row, "archived": value}])
    result = env.run("sessions", "--archived")
    assert result.returncode != 0
    assert str(env.home / ".codex" / "state_5.sqlite") in result.stderr and "archived" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads unreadable files")
def test_unreadable_claude_history_is_an_error_naming_the_file(env):
    path = env.home / ".claude" / "history.jsonl"
    path.chmod(0)
    result = env.run("sessions")
    assert result.returncode != 0
    assert str(path) in result.stderr and "Traceback" not in result.stderr


def test_missing_claude_history_is_an_error_naming_the_file(env):
    (env.home / ".claude-work" / "history.jsonl").unlink()
    result = env.run("sessions")
    assert result.returncode != 0
    assert str(env.home / ".claude-work" / "history.jsonl") in result.stderr


# --- launch -------------------------------------------------------------------------------


def test_launch_claude_personal_unsets_both_home_variables(env):
    project = env.project("alpha")
    claude_session(env.home / ".claude", SID, project)
    result = env.run("sessions", "-i", input="1\n", CLAUDE_CONFIG_DIR="/x", CODEX_HOME="/y")
    assert launched(result) == {"tool": "claude", "argv": ["--dangerously-skip-permissions", "--resume", SID],
                                "cwd": str(project), "CLAUDE_CONFIG_DIR": None, "CODEX_HOME": None}


def test_launch_claude_work_sets_claude_config_dir(env):
    project = env.project("alpha")
    claude_session(env.home / ".claude-work", SID, project)
    out = launched(env.run("sessions", "-i", input="1\n"))
    assert out["argv"] == ["--dangerously-skip-permissions", "--resume", SID]
    assert out["CLAUDE_CONFIG_DIR"] == str(env.home / ".claude-work")
    assert out["cwd"] == str(project)


def test_launch_codex_personal_puts_flags_before_resume(env):
    project = env.project("beta")
    codex_db(env.home / ".codex", [thread(env.home / ".codex", TID, project)])
    result = env.run("sessions", "-i", input="1\n", CLAUDE_CONFIG_DIR="/x", CODEX_HOME="/y")
    assert launched(result) == {"tool": "codex",
                                "argv": ["--no-daemon", "--dangerously-bypass-approvals-and-sandbox", "resume", TID],
                                "cwd": str(project), "CLAUDE_CONFIG_DIR": None, "CODEX_HOME": None}


def test_launch_codex_work_sets_codex_home(env):
    project = env.project("beta")
    codex_db(env.home / ".codex-work", [thread(env.home / ".codex-work", TID, project)])
    out = launched(env.run("sessions", "-i", input="1\n"))
    assert out["argv"] == ["--no-daemon", "--dangerously-bypass-approvals-and-sandbox", "resume", TID]
    assert out["CODEX_HOME"] == str(env.home / ".codex-work")


def test_numbered_prompt_picks_by_row_number(env):
    populate_all(env)
    listing = rows(env.run("sessions"))
    second = listing[1].split()
    out = launched(env.run("sessions", "-i", input="2\n"))
    assert out["tool"] == second[0]
    assert any(arg.startswith(second[2]) for arg in out["argv"])


@pytest.mark.parametrize("answer", ["", "0", "9", "x"])
def test_numbered_prompt_refuses_bad_answers(env, answer):
    claude_session(env.home / ".claude", SID, env.project("alpha"))
    result = env.run("sessions", "-i", input=answer + "\n")
    assert result.returncode != 0
    assert '"tool"' not in result.stdout


def test_fzf_picks_when_on_path(env):
    populate_all(env)
    env.script("fzf", FZF_STUB.format(python=sys.executable))
    listing = rows(env.run("sessions"))
    third = listing[2].split()
    out = launched(env.run("sessions", "-i", FZF_PICK="3"))
    assert out["tool"] == third[0]
    assert any(arg.startswith(third[2]) for arg in out["argv"])


def test_fzf_cancel_launches_nothing(env):
    populate_all(env)
    env.script("fzf", FZF_STUB.format(python=sys.executable))
    result = env.run("sessions", "-i")
    assert result.returncode != 0
    assert '"tool"' not in result.stdout


def test_launch_refuses_missing_cwd(env):
    gone = env.root / "removed"
    claude_session(env.home / ".claude", SID, gone)
    result = env.run("sessions", "-i", input="1\n")
    assert result.returncode != 0
    assert str(gone) in result.stderr
    assert '"tool"' not in result.stdout


def test_launch_refuses_claude_transcript_gone_after_listing(env):
    path = claude_session(env.home / ".claude", SID, env.project("alpha"))
    env.script("fzf", FZF_STUB.format(python=sys.executable))
    result = env.run("sessions", "-i", FZF_PICK="1", FZF_DELETE=str(path))
    assert result.returncode != 0
    assert str(path) in result.stderr
    assert '"tool"' not in result.stdout


def test_launch_refuses_codex_rollout_gone_after_listing(env):
    row = thread(env.home / ".codex", TID, env.project("beta"))
    codex_db(env.home / ".codex", [row])
    env.script("fzf", FZF_STUB.format(python=sys.executable))
    result = env.run("sessions", "-i", FZF_PICK="1", FZF_DELETE=row["rollout_path"])
    assert result.returncode != 0
    assert row["rollout_path"] in result.stderr
    assert '"tool"' not in result.stdout


def test_home_missing_from_launch_config_is_an_error(env, tmp_path):
    config = tmp_path / "launch.toml"
    config.write_text('[homes.claude]\nflags = []\n')
    codex_db(env.home / ".codex", [thread(env.home / ".codex", TID, env.project("beta"))])
    result = env.run("sessions", "-i", input="1\n", HQ_CONFIG=str(config))
    assert result.returncode != 0
    assert "codex" in result.stderr and str(config) in result.stderr
    assert '"tool"' not in result.stdout


def test_tracked_launch_config_matches_the_users_aliases():
    import tomllib
    data = tomllib.loads((TOOL.parent / "hq.toml").read_text())
    claude = ["--dangerously-skip-permissions"]
    codex = ["--no-daemon", "--dangerously-bypass-approvals-and-sandbox"]
    assert {home: entry["flags"] for home, entry in data["homes"].items()} == {
        "claude": claude, "claude-work": claude, "codex": codex, "codex-work": codex}


# --- colour ----------------------------------------------------------------------------

sys.path.insert(0, str(TOOL.parent))
from hq_cli import color  # noqa: E402

ANSI = re.compile(r"\x1b\[[0-9;]*m")
DARK = (0x1e, 0x1e, 0x1e)
LIGHT = (0xff, 0xff, 0xff)


def decode(channel: int) -> float:
    c = channel / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


CUBE = (0, 95, 135, 175, 215, 255)


def xterm256_rgb(index: int) -> tuple[int, int, int]:
    if index >= 232:
        gray = 8 + 10 * (index - 232)
        return gray, gray, gray
    index -= 16
    return CUBE[index // 36], CUBE[index // 6 % 6], CUBE[index % 6]


def oklab(rgb) -> tuple[float, float, float]:
    r, g, b = (decode(c) for c in rgb)
    l_ = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m_ = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s_ = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_)


def strip(text: str) -> str:
    return ANSI.sub("", text)


def populate_classes(env) -> None:
    """Every class: both harnesses, both homes, a gone cwd, an archived thread, a spread of ages."""
    populate_all(env)
    claude_session(env.home / ".claude", "cccccccc-3333-4333-8333-000000000003", env.root / "removed",
                   display="gone-cwd", age_s=3 * 86_400)
    history(env.home / ".claude", prompt("dddddddd-4444-4444-8444-000000000004", env.project("alpha"), "old"))
    transcript(env.home / ".claude", "dddddddd-4444-4444-8444-000000000004", age_s=200 * 86_400)
    worktree = env.project("beta") / ".worktrees" / "feature"
    worktree.mkdir(parents=True)
    claude_session(env.home / ".claude", "eeeeeeee-5555-4555-8555-000000000005", worktree, display="in-worktree",
                   age_s=7200)
    claude_session(env.home / ".claude", "ffffffff-6666-4666-8666-000000000006", env.project("beta") / ".worktrees"
                   / "removed", display="gone-worktree", age_s=7300)
    projects(env, be=env.project("beta"))


def test_color_never_and_auto_into_a_pipe_are_plain(env):
    populate_classes(env)
    for args in ((), ("--color", "auto"), ("--color", "never")):
        result = env.run("sessions", "--archived", *args, COLORTERM="truecolor")
        assert result.returncode == 0, result.stderr
        assert "\x1b" not in result.stdout


def test_color_never_wins_on_a_terminal(env):
    populate_classes(env)
    assert "\x1b" not in run_tty(env, "sessions", "--color", "never")


@pytest.mark.parametrize("colorterm", ["truecolor", "24bit", "", "xterm"])
def test_color_always_strips_to_the_plain_listing_exactly(env, colorterm):
    populate_classes(env)
    plain = env.run("sessions", "--archived", "--color", "never")
    painted = env.run("sessions", "--archived", "--color", "always", COLORTERM=colorterm)
    assert painted.returncode == 0, painted.stderr
    assert "\x1b[" in painted.stdout
    assert strip(painted.stdout) == plain.stdout


def test_color_depth_follows_colorterm(env):
    populate_classes(env)
    truecolor = env.run("sessions", "--color", "always", COLORTERM="truecolor").stdout
    fallback = env.run("sessions", "--color", "always").stdout
    assert "38;2;" in truecolor and "38;5;" not in truecolor
    assert "38;5;" in fallback and "38;2;" not in fallback


def test_color_always_ignores_no_color(env):
    populate_classes(env)
    assert "\x1b[" in env.run("sessions", "--color", "always", NO_COLOR="1").stdout


def run_tty(env, *args: str, **extra: str) -> str:
    """Run hq with stdout on a pseudo-terminal; returns what it wrote there."""
    leader, follower = pty.openpty()
    environment = {"HOME": str(env.home), "PATH": str(env.bin), **env.extra, **extra}
    process = subprocess.run([sys.executable, str(TOOL), *args], env=environment, stdout=follower,
                             stderr=subprocess.PIPE, text=True, cwd=env.root)
    os.close(follower)
    chunks = []
    while True:
        try:
            chunk = os.read(leader, 65536)
        except OSError:
            break
        if not chunk:
            break
        chunks.append(chunk)
    os.close(leader)
    assert process.returncode == 0, process.stderr
    return b"".join(chunks).decode()


def test_color_auto_paints_a_terminal(env):
    populate_classes(env)
    assert "\x1b[" in run_tty(env, "sessions")


@pytest.mark.parametrize("value, painted", [("1", False), ("", True)])
def test_color_auto_on_a_terminal_follows_no_color(env, value, painted):
    populate_classes(env)
    assert ("\x1b[" in run_tty(env, "sessions", NO_COLOR=value)) is painted


def row_for(output: str, text: str) -> str:
    return next(line for line in output.splitlines() if text in strip(line))


def test_color_classes(env):
    populate_classes(env)
    out = env.run("sessions", "--archived", "--color", "always", COLORTERM="truecolor").stdout
    painter = color.Painter("truecolor")
    claude, codex = painter.fg(color.CLAUDE), painter.fg(color.CODEX)
    assert f"\x1b[{claude}mclaude\x1b[0m" in row_for(out, "claude-personal")
    assert f"\x1b[{codex}mcodex\x1b[0m" in row_for(out, "codex-personal")
    work = f"\x1b[{color.BOLD};{painter.fg(color.WORK)}mwork\x1b[0m"
    assert work in row_for(out, "claude-work") and work in row_for(out, "codex-work")
    assert "\x1b[0m  personal  \x1b[" in row_for(out, "claude-personal")   # personal stays plain
    gone = row_for(out, "gone-cwd")
    assert f"\x1b[{painter.fg(color.MISSING)}m(cwd missing)\x1b[0m" in gone
    assert f"\x1b[{color.DIM}m{env.root / 'removed'}\x1b[0m" in gone
    archived = row_for(out, "codex-archived")
    cells = [cell for cell in ANSI.split(archived) if cell.strip()]
    codes = ANSI.findall(archived)
    openings = [code for code in codes if code != "\x1b[0m"]
    assert len(openings) == len(cells) and all(code.startswith(f"\x1b[{color.DIM};") or code == f"\x1b[{color.DIM}m"
                                               for code in openings)
    assert f"\x1b[{color.DIM};{codex}mcodex\x1b[0m" in archived


def test_color_worktree_name_is_dimmed(env):
    populate_classes(env)
    out = env.run("sessions", "--color", "always", COLORTERM="truecolor").stdout
    assert f"be\x1b[{color.DIM}m@feature\x1b[0m" in row_for(out, "in-worktree")
    gone = row_for(out, "gone-worktree")
    assert f"\x1b[{color.DIM}mbe\x1b[0m\x1b[{color.DIM}m@removed\x1b[0m" in gone


def test_color_age_cell_takes_the_age_colormap(env):
    populate_classes(env)
    out = env.run("sessions", "--color", "always", COLORTERM="truecolor").stdout
    painter = color.Painter("truecolor")
    old = row_for(out, " old")
    assert f"\x1b[{painter.age(200 * 86_400)}m" in old
    fresh = row_for(out, "claude-personal")
    assert f"\x1b[{painter.age(0)}mnow\x1b[0m" in fresh


def test_age_position_is_log_scaled_and_clamped():
    assert color.age_position(0) == color.age_position(color.AGE_MIN_S) == 0
    assert color.age_position(color.AGE_MAX_S) == color.age_position(10 * color.AGE_MAX_S) == 1
    hour, day = color.age_position(3600), color.age_position(86_400)
    assert 0.3 < hour < 0.4 and 0.6 < day < 0.7   # linear would put both near 0
    sweep = [color.age_position(color.AGE_MIN_S * 1.01 ** i) for i in range(1200)]
    assert all(a < b for a, b in zip(sweep, sweep[1:]) if b < 1)


def test_age_colormap_is_monotone_in_age():
    """24-bit lightness falls at every doubling of age (finer steps sit inside 8-bit
    rounding). The xterm-256 ladder is walked in order, every step used, and falls in
    chroma, then in lightness where chroma ties (the grays)."""
    doublings = [color.AGE_MIN_S * 2 ** i for i in range(18)]
    lightness = [oklab(color.age_colour(age).rgb)[0] for age in doublings]
    assert all(a > b for a, b in zip(lightness, lightness[1:])), lightness
    fine = [color.AGE_MIN_S * 1.02 ** i for i in range(700)]
    steps = [color.AGE_LADDER.index(color.age_colour(age).index) for age in fine]
    assert all(a <= b for a, b in zip(steps, steps[1:])) and set(steps) == set(range(len(color.AGE_LADDER)))
    # Equal log steps: under ~10m, 2h, 20h, 9d, older (README).
    ages = (5 * 60, 30 * 60, 6 * 3600, 3 * 86_400, 30 * 86_400)
    assert [color.age_colour(age).index for age in ages] == list(color.AGE_LADDER)
    span = color.AGE_MAX_S / color.AGE_MIN_S
    for step in range(1, len(color.AGE_LADDER)):
        edge = color.AGE_MIN_S * span ** (step / len(color.AGE_LADDER))
        assert color.age_colour(edge * 0.999).index == color.AGE_LADDER[step - 1]
        assert color.age_colour(edge * 1.001).index == color.AGE_LADDER[step]

    def chroma_lightness(index):
        lab = oklab(xterm256_rgb(index))
        return round((lab[1] ** 2 + lab[2] ** 2) ** 0.5, 2), lab[0]
    ladder = [chroma_lightness(index) for index in color.AGE_LADDER]
    assert ladder == sorted(ladder, reverse=True) and len(set(ladder)) == len(ladder)


def contrast(a, b) -> float:
    def luminance(rgb):
        r, g, b = (decode(c) for c in rgb)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    low, high = sorted((luminance(a), luminance(b)))
    return (high + 0.05) / (low + 0.05)


def test_colors_read_on_dark_and_light_backgrounds():
    ages = [color.AGE_MIN_S * 1.1 ** i for i in range(130)]
    colours = [color.CLAUDE, color.CODEX, color.WORK, color.MISSING, *map(color.age_colour, ages)]
    for rgb in [c.rgb for c in colours] + [xterm256_rgb(c.index) for c in colours]:
        assert contrast(rgb, DARK) >= 3 and contrast(rgb, LIGHT) >= 3, rgb


@pytest.mark.parametrize("pick", [lambda c: c.rgb, lambda c: xterm256_rgb(c.index)], ids=["truecolor", "256"])
def test_harness_hues_are_apart(pick):
    """The one pair of hues that share a column. Other pairs never sit side by side, so
    they need no floor (claude orange and the missing-cwd red are 10-11 apart)."""
    a, b = oklab(pick(color.CLAUDE)), oklab(pick(color.CODEX))
    assert 100 * sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5 >= 15


# Records its argv to $FZF_ARGS, then picks as FZF_STUB does.
FZF_RECORDING = """#!{python}
import json, os, sys
open(os.environ["FZF_ARGS"], "w").write(json.dumps(sys.argv[1:]))
lines = sys.stdin.read().splitlines()
open(os.environ["FZF_ARGS"] + ".input", "w").write("\\n".join(lines))
print(next(line for line in lines if line.split("\\t")[0] == os.environ["FZF_PICK"]))
"""


@pytest.mark.parametrize("when, painted", [("always", True), ("never", False)])
def test_fzf_gets_ansi_only_with_colour(env, tmp_path, when, painted):
    populate_all(env)
    env.script("fzf", FZF_RECORDING.format(python=sys.executable))
    record = tmp_path / "fzf-args.json"
    out = launched(env.run("sessions", "-i", "--color", when, FZF_PICK="1", FZF_ARGS=str(record)))
    assert out["tool"] in ("claude", "codex")
    assert ("--ansi" in json.loads(record.read_text())) is painted
    assert ("\x1b[" in Path(str(record) + ".input").read_text()) is painted


def test_numbered_prompt_is_painted_like_the_listing(env):
    populate_all(env)
    listing = env.run("sessions", "--color", "always").stdout.splitlines()[:-1]
    result = env.run("sessions", "-i", "--color", "always", input="1\n")
    assert result.returncode == 0, result.stderr
    assert all(f"{n:>3}  {line}" in result.stdout for n, line in enumerate(listing, 1))
    assert "\x1b[" in result.stdout
