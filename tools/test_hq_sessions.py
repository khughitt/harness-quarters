"""`hq sessions` over synthetic homes under a temp HOME, launching stub `claude`/`codex`
executables that print their argv, cwd and both home variables as JSON."""
import json
import os
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
            "recency_at_ms": NOW_MS - int(age_s * 1000), "name": None, "title": "a title", **fields}


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
