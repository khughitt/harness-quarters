"""live-picks saves the model and effort picks in local/ and puts back what a git command dropped."""
import ast
import contextlib
import fcntl
import json
import os
import select
import signal
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path

import pytest

HOOKS = Path(__file__).parent
HOOK_FILES = ("harness-state-clean", "harness_state.py", "codex-trust", "live-picks",
              "harness-state-refresh", "post-checkout", "post-merge", "post-rewrite")
CLAUDE = "claude/settings.json"
CODEX = "codex/config.toml"
PI = "pi/settings.json"
PI_BASE = {"lastChangelogVersion": "1.1.0", "theme": "system"}
PI_VALUES = {"defaultProvider": "anthropic", "defaultModel": "claude-opus-5-5",
             "defaultThinkingLevel": "high"}
PI_SET = {"state": "set", "values": PI_VALUES}
BASE = "[features]\nhooks = true\n"
TUI = "[tui]\nx = 1\n"
PICK = 'model = "gpt-6.1-sol"\nmodel_reasoning_effort = "high"\n'
PICK_LINES = ['model = "gpt-6.1-sol"\n', 'model_reasoning_effort = "high"\n']
A = '[projects."/work/a"]\ntrust_level = "trusted"\n'


def git(repo, *args, check=True):
    return subprocess.run(["git", "-C", str(repo), *args], check=check, text=True,
                          capture_output=True)


def write_claude(repo, **settings):
    data = {"theme": "dark-ansi", **settings}
    (repo / CLAUDE).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def write_pi(repo, **settings):
    (repo / PI).write_text(json.dumps({**PI_BASE, **settings}, indent=2) + "\n")


@pytest.fixture
def repo(tmp_path):
    """A main checkout shaped like this one: the filter, the hooks, both configs, local/."""
    repo = tmp_path / "hq"
    (repo / ".githooks").mkdir(parents=True)
    for name in HOOK_FILES:
        shutil.copy2(HOOKS / name, repo / ".githooks" / name)
    (repo / "claude").mkdir()
    (repo / "codex").mkdir()
    (repo / "pi").mkdir()
    (repo / "local" / "codex").mkdir(parents=True)
    (repo / ".gitattributes").write_text("claude/settings*.json filter=harness-state\n"
                                         "codex/config*.toml filter=harness-state\n"
                                         "pi/settings*.json filter=harness-state\n")
    (repo / ".gitignore").write_text("local/\n__pycache__/\n")
    write_claude(repo)
    (repo / CODEX).write_text(BASE)
    write_pi(repo)
    git(tmp_path, "init", "-q", "-b", "main", str(repo))
    git(repo, "config", "filter.harness-state.clean", ".githooks/harness-state-clean %f")
    git(repo, "config", "core.hooksPath", ".githooks")
    git(repo, "config", "user.email", "t@example.invalid")
    git(repo, "config", "user.name", "t")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def picks(repo, *args):
    """Run live-picks as the hooks do: by path, from another directory."""
    return subprocess.run([str(repo / ".githooks" / "live-picks"), *args], cwd=repo.parent,
                          text=True, capture_output=True)


def record_path(repo):
    return repo / "local" / "live-picks.json"


def record(repo):
    path = record_path(repo)
    return json.loads(path.read_text()) if path.exists() else None


def claude(repo):
    return json.loads((repo / CLAUDE).read_text())


def codex(repo):
    return tomllib.loads((repo / CODEX).read_text())


def clean(repo, name, text):
    return subprocess.run([str(repo / ".githooks" / "harness-state-clean"), name],
                          input=text, check=True, text=True, capture_output=True).stdout


def status(repo):
    return git(repo, "status", "--porcelain").stdout


def save(repo, **entries):
    record_path(repo).write_text(json.dumps(entries) + "\n")


CLAUDE_SET = {"state": "set", "values": {"model": "opus"}}
CODEX_SET = {"state": "set", "lines": PICK_LINES}


def saved_both(repo):
    save(repo, **{CLAUDE: CLAUDE_SET, CODEX: CODEX_SET})


def test_capture_saves_the_pick_each_file_holds(repo):
    write_claude(repo, model="opus")
    (repo / CODEX).write_text(PICK + BASE)

    result = picks(repo, "capture")

    assert result.returncode == 0, result.stderr
    assert record(repo) == {CLAUDE: CLAUDE_SET, CODEX: CODEX_SET}


def test_capture_with_no_pick_anywhere_creates_no_record(repo):
    assert picks(repo, "capture").returncode == 0

    assert record(repo) is None


def test_capture_of_a_file_holding_no_pick_keeps_the_saved_one(repo):
    saved_both(repo)

    assert picks(repo, "capture").returncode == 0

    assert record(repo) == {CLAUDE: CLAUDE_SET, CODEX: CODEX_SET}


def test_a_later_pick_replaces_the_saved_one(repo):
    saved_both(repo)
    write_claude(repo, model="sonnet")

    assert picks(repo, "capture").returncode == 0
    write_claude(repo)
    assert picks(repo, "restore").returncode == 0

    assert claude(repo)["model"] == "sonnet"


def test_a_partial_pick_is_saved_as_is_and_never_completed(repo):
    write_claude(repo, model="opus", modelSettings={"opus": {"context": "1m"}})
    assert picks(repo, "capture").returncode == 0
    write_claude(repo, model="haiku")

    assert picks(repo, "sync").returncode == 0

    assert record(repo)[CLAUDE] == {"state": "set", "values": {"model": "haiku"}}
    assert "modelSettings" not in claude(repo)


@pytest.mark.parametrize("new, kept", [({"effortLevel": "low"}, {"model": "opus"}),
                                       ({"model": "sonnet"}, {"effortLevel": "high"})])
def test_a_pick_of_one_claude_picker_keeps_the_other_pickers_saved_value(repo, new, kept):
    save(repo, **{CLAUDE: {"state": "set", "values": {"model": "opus", "effortLevel": "high"}}})
    write_claude(repo, **new)

    result = picks(repo, "sync")

    assert result.returncode == 0, result.stderr
    assert record(repo)[CLAUDE] == {"state": "set", "values": {**kept, **new}}
    assert claude(repo) == {"theme": "dark-ansi", **kept, **new}


def test_restore_fills_only_the_claude_picker_the_file_lacks(repo):
    save(repo, **{CLAUDE: {"state": "set", "values": {"model": "opus", "effortLevel": "high"}}})
    write_claude(repo, effortLevel="low")

    assert picks(repo, "restore").returncode == 0

    assert claude(repo) == {"theme": "dark-ansi", "effortLevel": "low", "model": "opus"}


def test_forget_of_claude_resets_both_model_and_effort(repo):
    write_claude(repo, model="opus", effortLevel="high")
    assert picks(repo, "capture").returncode == 0

    result = picks(repo, "forget", CLAUDE)

    assert result.returncode == 0, result.stderr
    assert claude(repo) == {"theme": "dark-ansi"}
    assert record(repo)[CLAUDE] == {"state": "default"}
    assert status(repo) == ""


def test_restore_puts_back_both_picks_and_keeps_what_git_stages(repo):
    saved_both(repo)
    write_claude(repo, theme="light")
    (repo / CODEX).write_text(TUI + BASE)
    before = {name: (repo / name).read_text() for name in (CLAUDE, CODEX)}

    result = picks(repo, "restore")

    assert result.returncode == 0, result.stderr
    assert claude(repo) == {"theme": "light", "model": "opus"}
    assert (repo / CODEX).read_text() == PICK + TUI + BASE
    for name in (CLAUDE, CODEX):
        assert clean(repo, name, (repo / name).read_text()) == clean(repo, name, before[name])


def test_restore_never_overwrites_a_pick(repo):
    saved_both(repo)
    write_claude(repo, model="sonnet")
    inode = (repo / CLAUDE).stat().st_ino

    assert picks(repo, "restore").returncode == 0

    assert claude(repo)["model"] == "sonnet"
    assert (repo / CLAUDE).stat().st_ino == inode


def test_restore_prepends_codex_lines_before_a_header_like_string_line(repo):
    save(repo, **{CODEX: CODEX_SET})
    notice = 'notice = """\n[example]\n"""\n'
    (repo / CODEX).write_text(notice + BASE)

    result = picks(repo, "restore")

    assert result.returncode == 0, result.stderr
    assert codex(repo)["notice"] == "[example]\n"
    assert codex(repo)["model"] == "gpt-6.1-sol"


def test_restore_with_no_record_or_a_default_one_writes_nothing(repo):
    assert picks(repo, "restore").returncode == 0
    save(repo, **{CLAUDE: {"state": "default"}})

    assert picks(repo, "restore").returncode == 0

    assert "model" not in claude(repo)


def test_a_sync_that_changes_nothing_writes_nothing(repo):
    write_claude(repo, model="opus")
    (repo / CODEX).write_text(PICK + BASE)
    assert picks(repo, "sync").returncode == 0
    paths = [repo / CLAUDE, repo / CODEX, record_path(repo)]
    before = [(p.stat().st_ino, p.stat().st_mtime_ns) for p in paths]

    assert picks(repo, "sync").returncode == 0

    assert [(p.stat().st_ino, p.stat().st_mtime_ns) for p in paths] == before


@pytest.mark.parametrize("text", [
    "{", "[]", '{"other.json": {"state": "default"}}',
    '{"claude/settings.json": {"state": "maybe"}}',
    '{"claude/settings.json": {"state": "set", "values": {"theme": "x"}}}',
    '{"claude/settings.json": {"state": "default", "values": {}}}',
    '{"codex/config.toml": {"state": "set", "lines": ["theme = 1\\n"]}}',
    '{"codex/config.toml": {"state": "set", "lines": ["model = \\"x\\""]}}',
])
def test_an_invalid_record_is_refused_and_left_alone(repo, text):
    record_path(repo).write_text(text)
    write_claude(repo, model="opus")
    before = (repo / CLAUDE).read_text()

    result = picks(repo, "sync")

    assert result.returncode != 0
    assert "live-picks: local/live-picks.json" in result.stderr
    assert record_path(repo).read_text() == text
    assert (repo / CLAUDE).read_text() == before


def test_an_unparsable_file_is_refused_and_the_other_still_restored(repo):
    saved_both(repo)
    (repo / CLAUDE).write_text("{\n")

    result = picks(repo, "restore")

    assert result.returncode != 0
    assert "claude/settings.json does not parse" in result.stderr
    assert (repo / CLAUDE).read_text() == "{\n"
    assert codex(repo)["model"] == "gpt-6.1-sol"


def test_a_codex_pick_spanning_lines_is_refused(repo):
    (repo / CODEX).write_text('model = """\ngpt\n"""\n' + BASE)

    result = picks(repo, "capture")

    assert result.returncode != 0
    assert "one-line keys" in result.stderr
    assert record(repo) is None


def test_forget_records_the_default_and_removes_the_pick(repo):
    write_claude(repo, model="opus", modelSettings={"x": 1})
    (repo / CODEX).write_text(PICK + BASE)
    assert picks(repo, "capture").returncode == 0
    before = {name: clean(repo, name, (repo / name).read_text()) for name in (CLAUDE, CODEX)}

    for name in (CLAUDE, CODEX):
        result = picks(repo, "forget", name)
        assert result.returncode == 0, result.stderr

    assert record(repo) == {CLAUDE: {"state": "default"}, CODEX: {"state": "default"}}
    assert claude(repo) == {"theme": "dark-ansi"}
    assert (repo / CODEX).read_text() == BASE
    for name in (CLAUDE, CODEX):
        assert clean(repo, name, (repo / name).read_text()) == before[name]
    assert status(repo) == ""


@pytest.mark.parametrize("name", [CLAUDE, CODEX])
def test_forget_survives_a_later_git_rewrite(repo, name):
    write_claude(repo, model="opus")
    (repo / CODEX).write_text(PICK + BASE)
    assert picks(repo, "capture").returncode == 0
    assert picks(repo, "forget", name).returncode == 0
    if name == CLAUDE:
        write_claude(repo, theme="light")
    else:
        (repo / CODEX).write_text(TUI + BASE)

    git(repo, "checkout", "--", name)
    assert picks(repo, "restore").returncode == 0

    assert record(repo)[name] == {"state": "default"}
    live = claude(repo) if name == CLAUDE else codex(repo)
    assert "model" not in live
    assert "modelSettings" not in live
    assert "model_reasoning_effort" not in live


def test_a_filesystem_error_fails_cleanly(repo):
    record_path(repo).mkdir()

    result = picks(repo, "sync")

    assert result.returncode != 0
    assert "live-picks: " in result.stderr
    assert "Traceback" not in result.stderr


def test_forget_of_a_file_it_does_not_own_is_refused(repo):
    result = picks(repo, "forget", "claude/settings.work.json")

    assert result.returncode != 0
    assert "forget takes" in result.stderr


def test_concurrent_syncs_of_both_tools_keep_trust_and_the_pick(repo):
    (repo / "local" / "codex" / "trust.toml").write_text(A)
    save(repo, **{CODEX: CODEX_SET})
    tools = ("codex-trust", "live-picks") * 6
    runs = [subprocess.Popen([str(repo / ".githooks" / tool), "sync"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for tool in tools]

    for run in runs:
        _, err = run.communicate()
        assert run.returncode == 0, err

    text = (repo / CODEX).read_text()
    assert text.count("model = ") == 1
    assert text.count('[projects."/work/a"]') == 1
    assert codex(repo)["model"] == "gpt-6.1-sol"


def test_a_linked_worktree_is_refused(repo, tmp_path):
    other = tmp_path / "other"
    git(repo, "worktree", "add", "-q", "-b", "other", str(other))
    (other / "local").mkdir()

    result = picks(other, "capture")

    assert result.returncode != 0
    assert "linked worktree" in result.stderr


def test_a_missing_local_directory_names_just_setup(repo):
    shutil.rmtree(repo / "local")

    result = picks(repo, "capture")

    assert result.returncode != 0
    assert "just setup" in result.stderr


def test_a_missing_owned_file_is_named(repo):
    (repo / CODEX).unlink()

    result = picks(repo, "capture")

    assert result.returncode != 0
    assert "codex/config.toml is missing" in result.stderr


@pytest.mark.parametrize("args", [(), ("prune",), ("capture", "--all"), ("capture", "--explicit"), ("hook", "pre-push"),
                                  ("forget",)])
def test_bad_usage_prints_the_usage(repo, args):
    result = picks(repo, *args)

    assert result.returncode != 0
    assert "usage: live-picks" in result.stderr


# Review Focus 1-5


def test_restore_keeps_non_ascii_settings(repo):
    save(repo, **{CLAUDE: CLAUDE_SET})
    write_claude(repo, statusLine={"glyph": "café ▸"})
    before = clean(repo, CLAUDE, (repo / CLAUDE).read_text())

    assert picks(repo, "restore").returncode == 0

    assert claude(repo)["statusLine"] == {"glyph": "café ▸"}
    assert clean(repo, CLAUDE, (repo / CLAUDE).read_text()) == before


def test_a_nested_model_settings_round_trips(repo):
    settings = {"opus": {"context": "1m", "betas": ["a", "b"]}}
    write_claude(repo, model="opus", modelSettings=settings)
    assert picks(repo, "capture").returncode == 0
    write_claude(repo)

    assert picks(repo, "restore").returncode == 0

    assert claude(repo)["modelSettings"] == settings


def test_a_codex_pick_with_a_trailing_comment_round_trips(repo):
    line = 'model = "gpt-6.1-sol"  # picked\n'
    (repo / CODEX).write_text(line + BASE)
    assert picks(repo, "capture").returncode == 0
    (repo / CODEX).write_text(BASE)

    assert picks(repo, "restore").returncode == 0

    assert (repo / CODEX).read_text() == line + BASE


def test_restore_into_a_codex_file_with_no_header_or_final_newline(repo):
    save(repo, **{CODEX: CODEX_SET})
    (repo / CODEX).write_text('personality = "p"')
    before = clean(repo, CODEX, 'personality = "p"')

    assert picks(repo, "restore").returncode == 0

    assert codex(repo) == {"model": "gpt-6.1-sol", "model_reasoning_effort": "high",
                           "personality": "p"}
    assert clean(repo, CODEX, (repo / CODEX).read_text()) == before


def test_restore_keeps_a_home_link_and_the_file_mode(repo, tmp_path):
    save(repo, **{CLAUDE: CLAUDE_SET})
    os.chmod(repo / CLAUDE, 0o600)
    home = tmp_path / "home-settings.json"
    home.symlink_to(repo / CLAUDE)

    assert picks(repo, "restore").returncode == 0

    assert home.is_symlink()
    assert json.loads(home.read_text())["model"] == "opus"
    assert (repo / CLAUDE).stat().st_mode & 0o777 == 0o600


def test_capture_keeps_a_new_pick_when_the_other_file_is_missing(repo):
    saved_both(repo)
    write_claude(repo, model="sonnet")
    (repo / CODEX).unlink()

    result = picks(repo, "capture")

    assert result.returncode != 0
    assert CODEX in result.stderr
    assert record(repo)[CLAUDE] == {"state": "set", "values": {"model": "sonnet"}}
    assert record(repo)[CODEX] == CODEX_SET


@pytest.mark.parametrize("damage", ["missing", "bad_utf8"])
def test_restore_handles_the_healthy_file_after_a_live_read_failure(repo, damage):
    saved_both(repo)
    if damage == "missing":
        (repo / CLAUDE).unlink()
    else:
        (repo / CLAUDE).write_bytes(b"\xff")

    result = picks(repo, "restore")

    assert result.returncode != 0
    assert CLAUDE in result.stderr
    assert "Traceback" not in result.stderr
    assert codex(repo)["model"] == "gpt-6.1-sol"
    assert record(repo)[CLAUDE] == CLAUDE_SET


def fail_live_tempfile(repo, name):
    """Inject failure at tempfile creation; every other CLI operation stays real."""
    tool = repo / ".githooks" / "live-picks"
    source = tool.with_name("live-picks-source")
    shutil.copy2(tool, source)
    tool.write_text(f"""#!/usr/bin/env python3
import runpy
from pathlib import Path
import harness_state

here = Path(__file__).resolve().parent
create = harness_state.tempfile.mkstemp

def fail_target(*args, **kwargs):
    if Path(kwargs["dir"]) == (here.parent / {name!r}).parent:
        raise PermissionError("simulated live-file write failure")
    return create(*args, **kwargs)

harness_state.tempfile.mkstemp = fail_target
runpy.run_path(str(here / "live-picks-source"), run_name="__main__")
""")


def test_restore_handles_the_healthy_file_after_a_live_write_failure(repo):
    saved_both(repo)
    fail_live_tempfile(repo, CLAUDE)

    result = picks(repo, "restore")

    assert result.returncode != 0
    assert CLAUDE in result.stderr
    assert claude(repo) == {"theme": "dark-ansi"}
    assert codex(repo)["model"] == "gpt-6.1-sol"


def test_hook_restages_a_restored_file_when_the_other_write_fails(repo):
    saved_both(repo)
    fail_live_tempfile(repo, CODEX)

    result = picks(repo, "hook", "post-merge")

    assert result.returncode == 0
    assert CODEX in result.stderr
    assert "Traceback" not in result.stderr
    assert claude(repo)["model"] == "opus"
    assert "model" not in codex(repo)
    assert git(repo, "diff-files", "--name-only", "--", CLAUDE).stdout == ""


def picked(repo):
    """Both harnesses picked and a turn ended: picks live, saved, git's mark clear."""
    write_claude(repo, **{**claude(repo), "model": "opus"})
    (repo / CODEX).write_text(PICK + (repo / CODEX).read_text())
    assert picks(repo, "capture").returncode == 0
    git(repo, "add", "--", CLAUDE, CODEX)


def commit_settings(repo, message, theme="light", codex_text=TUI + BASE):
    write_claude(repo, theme=theme)
    (repo / CODEX).write_text(codex_text)
    git(repo, "add", "--", CLAUDE, CODEX)
    git(repo, "commit", "-q", "-m", message)


def side_with_settings(repo):
    git(repo, "switch", "-q", "-c", "side")
    commit_settings(repo, "side")
    git(repo, "switch", "-q", "main")


def assert_picked(repo, theme="light", codex_text=TUI + BASE):
    assert claude(repo) == {"theme": theme, "model": "opus"}
    assert (repo / CODEX).read_text() == PICK + codex_text


def test_a_merge_that_rewrites_both_configs_keeps_both_picks(repo):
    side_with_settings(repo)
    picked(repo)

    result = git(repo, "merge", "-q", "side")

    assert result.stderr == ""
    assert_picked(repo)
    assert status(repo) == ""


def test_a_merge_keeps_an_effort_pick_with_the_model_pick(repo):
    side_with_settings(repo)
    write_claude(repo, model="opus", effortLevel="xhigh")
    assert picks(repo, "capture").returncode == 0
    git(repo, "add", "--", CLAUDE)

    git(repo, "merge", "-q", "side")

    assert claude(repo) == {"theme": "light", "model": "opus", "effortLevel": "xhigh"}
    assert status(repo) == ""


def test_one_merge_restores_trust_and_picks_together(repo):
    side_with_settings(repo)
    picked(repo)
    (repo / "local" / "codex" / "trust.toml").write_text(A)

    git(repo, "merge", "-q", "side")

    assert codex(repo)["projects"] == {"/work/a": {"trust_level": "trusted"}}
    assert codex(repo)["model"] == "gpt-6.1-sol"
    assert status(repo) == ""


def test_a_branch_switch_keeps_the_picks_both_ways(repo):
    side_with_settings(repo)
    picked(repo)

    git(repo, "switch", "-q", "side")
    assert_picked(repo)
    git(repo, "switch", "-q", "main")

    assert_picked(repo, theme="dark-ansi", codex_text=BASE)
    assert status(repo) == ""


@pytest.mark.parametrize("command", [("checkout", "--"), ("restore",)])
def test_a_checkout_of_a_file_keeps_its_pick(repo, command):
    picked(repo)
    write_claude(repo, theme="light", model="opus")

    git(repo, *command, CLAUDE)

    assert claude(repo) == {"theme": "dark-ansi", "model": "opus"}
    assert status(repo) == ""


def test_a_rebase_that_replays_a_settings_commit_keeps_the_picks(repo):
    git(repo, "switch", "-q", "-c", "side")
    (repo / "u").write_text("side\n")
    git(repo, "add", "u")
    git(repo, "commit", "-q", "-m", "side")
    git(repo, "switch", "-q", "main")
    commit_settings(repo, "main settings")
    picked(repo)

    result = git(repo, "rebase", "side", check=False)

    assert result.returncode == 0, result.stderr
    assert_picked(repo)
    assert "model" not in git(repo, "show", "HEAD:" + CLAUDE).stdout
    assert status(repo) == ""


@pytest.mark.parametrize("command", ["checkout --", "switch", "merge"])
def test_hooks_leave_a_linked_worktree_alone(repo, tmp_path, command):
    side_with_settings(repo)
    picked(repo)
    other = tmp_path / "other"
    git(repo, "worktree", "add", "-q", "-b", "mine", str(other), "main")
    if command == "checkout --":
        (other / CLAUDE).write_text('{"theme": "x"}\n')
        result = git(other, "checkout", "-q", "--", CLAUDE)
    elif command == "switch":
        result = git(other, "switch", "-q", "--detach", "side")
    else:
        result = git(other, "merge", "-q", "side")

    assert result.stderr == ""
    assert "model" not in (other / CLAUDE).read_text()
    assert "model" not in (other / CODEX).read_text()
    assert git(other, "status", "--porcelain").stdout == ""


def test_a_filesystem_error_in_a_hook_reports_and_lets_the_git_command_succeed(repo):
    side_with_settings(repo)
    picked(repo)
    record_path(repo).unlink()
    record_path(repo).mkdir()

    result = git(repo, "switch", "-q", "side", check=False)

    assert result.returncode == 0
    assert "live-picks: " in result.stderr
    assert "Traceback" not in result.stderr
    assert git(repo, "branch", "--show-current").stdout.strip() == "side"



@pytest.mark.parametrize("damage", ["missing", "non-executable", "startup-failure"])
def test_a_pick_launch_failure_keeps_a_successful_checkout_successful(repo, damage):
    side_with_settings(repo)
    tool = repo / ".githooks" / "live-picks"
    if damage == "missing":
        tool.unlink()
    elif damage == "non-executable":
        tool.chmod(0o644)
    else:
        tool.write_text("#!/bin/sh\necho 'live-picks: startup failed' >&2\nexit 1\n")

    result = git(repo, "switch", "-q", "side", check=False)

    assert result.returncode == 0, result.stderr
    assert "live-picks" in result.stderr
    assert git(repo, "branch", "--show-current").stdout.strip() == "side"
    assert claude(repo) == {"theme": "light"}
    assert (repo / CODEX).read_text() == TUI + BASE


@pytest.mark.parametrize("hook", ["post-checkout", "post-merge", "post-rewrite"])
@pytest.mark.parametrize("damage", ["missing", "non-executable", "startup-failure"])
def test_git_wrappers_keep_zero_status_when_pick_launch_fails(repo, hook, damage):
    tool = repo / ".githooks" / "live-picks"
    if damage == "missing":
        tool.unlink()
    elif damage == "non-executable":
        tool.chmod(0o644)
    else:
        tool.write_text("#!/bin/sh\necho 'live-picks: startup failed' >&2\nexit 1\n")

    result = subprocess.run([str(repo / ".githooks" / hook)], cwd=repo,
                            input="old new\n", text=True, capture_output=True)

    assert result.returncode == 0, result.stderr
    assert "live-picks" in result.stderr


def test_a_failing_pick_restore_reports_and_trust_still_returns(repo):
    side_with_settings(repo)
    picked(repo)
    (repo / "local" / "codex" / "trust.toml").write_text(A)
    record_path(repo).write_text("{")

    result = git(repo, "switch", "-q", "side", check=False)

    assert result.returncode == 0
    assert "live-picks: local/live-picks.json" in result.stderr
    assert "the next turn end retries" in result.stderr
    assert "/work/a" in codex(repo)["projects"]
    assert git(repo, "branch", "--show-current").stdout.strip() == "side"


def refresh(repo):
    """Run the refresh as a harness hook does: from another directory, payload on stdin."""
    return subprocess.run([str(repo / ".githooks" / "harness-state-refresh")],
                          cwd=repo.parent, input=json.dumps({"hook_event_name": "Stop"}),
                          text=True, capture_output=True)


def index_lock(repo):
    return Path(git(repo, "rev-parse", "--path-format=absolute", "--git-path",
                    "index.lock").stdout.strip())


def test_the_stop_hook_saves_a_new_pick(repo):
    write_claude(repo, model="opus")

    result = refresh(repo)

    assert result.returncode == 0, result.stderr
    assert record(repo)[CLAUDE] == CLAUDE_SET
    assert status(repo) == ""


def dirty(repo):
    """Give both files a real change, so a reset or stash rewrites them; picks kept."""
    write_claude(repo, theme="light", model="opus")
    (repo / CODEX).write_text(TUI + (repo / CODEX).read_text())


def test_the_stop_hook_restores_the_picks_after_a_hard_reset(repo):
    picked(repo)
    dirty(repo)
    git(repo, "reset", "-q", "--hard")
    assert "model" not in claude(repo)

    result = refresh(repo)

    assert result.returncode == 0, result.stderr
    assert_picked(repo, theme="dark-ansi", codex_text=BASE)
    assert status(repo) == ""


def test_the_stop_hook_restores_an_effort_pick_made_without_a_model_pick(repo):
    write_claude(repo, effortLevel="low")
    assert picks(repo, "capture").returncode == 0
    write_claude(repo, theme="light", effortLevel="low")
    git(repo, "reset", "-q", "--hard")
    assert "effortLevel" not in claude(repo)

    result = refresh(repo)

    assert result.returncode == 0, result.stderr
    assert record(repo)[CLAUDE] == {"state": "set", "values": {"effortLevel": "low"}}
    assert claude(repo) == {"theme": "dark-ansi", "effortLevel": "low"}
    assert status(repo) == ""


def test_the_stop_hook_restores_the_picks_after_a_stash_round_trip(repo):
    picked(repo)
    write_claude(repo, theme="light", model="opus")
    git(repo, "stash", "-q")
    git(repo, "stash", "pop", "-q")
    assert "model" not in claude(repo)

    assert refresh(repo).returncode == 0

    assert claude(repo) == {"theme": "light", "model": "opus"}
    assert "model" not in git(repo, "diff", "--", CLAUDE).stdout


def test_the_stop_hook_restores_during_a_merge_stopped_on_a_conflict(repo):
    (repo / "u").write_text("base\n")
    git(repo, "add", "u")
    git(repo, "commit", "-q", "-m", "u")
    git(repo, "switch", "-q", "-c", "side")
    (repo / "u").write_text("side\n")
    git(repo, "add", "u")
    commit_settings(repo, "side")
    git(repo, "switch", "-q", "main")
    (repo / "u").write_text("main\n")
    git(repo, "add", "u")
    git(repo, "commit", "-q", "-m", "main")
    picked(repo)
    assert git(repo, "merge", "-q", "side", check=False).returncode == 1

    assert refresh(repo).returncode == 0

    assert_picked(repo)
    (repo / "u").write_text("both\n")
    git(repo, "add", "u")
    git(repo, "commit", "-q", "--no-edit")
    assert "model" not in git(repo, "show", "HEAD:" + CLAUDE).stdout
    assert '"theme": "light"' in git(repo, "show", "HEAD:" + CLAUDE).stdout
    assert status(repo) == ""


def test_a_picker_reset_without_forget_is_restored_at_stop(repo):
    picked(repo)
    write_claude(repo)

    result = refresh(repo)

    assert result.returncode == 0, result.stderr
    assert record(repo)[CLAUDE] == CLAUDE_SET
    assert claude(repo)["model"] == "opus"
    assert codex(repo)["model"] == "gpt-6.1-sol"

def test_a_new_claude_pick_after_codex_lost_its_pick_keeps_and_restores_it(repo):
    picked(repo)
    dirty(repo)
    git(repo, "reset", "-q", "--hard")
    write_claude(repo, model="sonnet")

    result = refresh(repo)

    assert result.returncode == 0, result.stderr
    assert record(repo)[CODEX] == CODEX_SET
    assert record(repo)[CLAUDE] == {"state": "set", "values": {"model": "sonnet"}}
    assert codex(repo)["model"] == "gpt-6.1-sol"

@pytest.mark.parametrize("name", [CLAUDE, CODEX])
def test_forget_while_the_index_is_locked_records_a_reset_that_stop_keeps(repo, name):
    picked(repo)
    before_index = git(repo, "write-tree").stdout
    lock = index_lock(repo)
    lock.write_text("")

    result = picks(repo, "forget", name)

    assert result.returncode == 0, result.stderr
    assert lock.read_text() == ""
    assert record(repo)[name] == {"state": "default"}
    assert clean(repo, name, (repo / name).read_text()) == (repo / name).read_text()
    lock.unlink()
    assert git(repo, "write-tree").stdout == before_index
    assert refresh(repo).returncode == 0
    live = claude(repo) if name == CLAUDE else codex(repo)
    assert "model" not in live
    assert record(repo)[name] == {"state": "default"}

@pytest.mark.parametrize("name", [CLAUDE, CODEX])
def test_stop_saves_a_changed_pick_even_while_the_index_is_locked(repo, name):
    picked(repo)
    if name == CLAUDE:
        write_claude(repo, model="sonnet")
        want = {"state": "set", "values": {"model": "sonnet"}}
    else:
        lines = ['model = "gpt-6-astra"\n', 'model_reasoning_effort = "medium"\n']
        (repo / CODEX).write_text("".join(lines) + BASE)
        want = {"state": "set", "lines": lines}
    before_index = git(repo, "write-tree").stdout
    lock = index_lock(repo)
    lock.write_text("")

    result = refresh(repo)

    assert result.returncode == 0, result.stderr
    assert record(repo)[name] == want
    assert lock.exists()
    lock.unlink()
    assert git(repo, "write-tree").stdout == before_index


def test_a_turn_end_with_the_index_locked_saves_but_does_not_restore(repo):
    picked(repo)
    dirty(repo)
    git(repo, "reset", "-q", "--hard")
    lock = index_lock(repo)
    lock.write_text("")

    assert refresh(repo).returncode == 0

    assert "model" not in claude(repo)
    lock.unlink()
    assert refresh(repo).returncode == 0
    assert claude(repo)["model"] == "opus"


def test_a_failed_capture_fails_the_hook_after_the_other_steps(repo):
    picked(repo)
    (repo / "local" / "codex" / "trust.toml").write_text(A)
    dirty(repo)
    git(repo, "reset", "-q", "--hard")
    (repo / CLAUDE).write_text("{\n")

    result = refresh(repo)

    assert result.returncode != 0
    assert "claude/settings.json does not parse" in result.stderr
    assert codex(repo)["model"] == "gpt-6.1-sol"
    assert "/work/a" in codex(repo)["projects"]


def test_a_missing_pick_tool_does_not_prevent_trust_recovery_or_staging(repo):
    write_claude(repo, model="sonnet")
    (repo / "local" / "codex" / "trust.toml").write_text(A)
    (repo / ".githooks" / "live-picks").unlink()

    result = refresh(repo)

    assert result.returncode != 0
    assert "live-picks capture" in result.stderr
    assert "live-picks restore" in result.stderr
    assert "Traceback" not in result.stderr
    assert codex(repo)["projects"] == {"/work/a": {"trust_level": "trusted"}}
    assert claude(repo)["model"] == "sonnet"
    assert git(repo, "diff-files", "--name-only", "--", CLAUDE, CODEX).stdout == ""


@pytest.mark.parametrize("damage", ["missing", "not_executable"])
def test_a_trust_launch_failure_does_not_prevent_pick_restoration(repo, damage):
    picked(repo)
    dirty(repo)
    git(repo, "reset", "-q", "--hard")
    trust = repo / ".githooks" / "codex-trust"
    if damage == "missing":
        trust.unlink()
    else:
        trust.chmod(0o600)

    result = refresh(repo)

    assert result.returncode != 0
    assert "codex-trust sync" in result.stderr
    assert "Traceback" not in result.stderr
    assert_picked(repo, theme="dark-ansi", codex_text=BASE)
    assert git(repo, "diff-files", "--name-only", "--", CLAUDE, CODEX).stdout == ""


def test_a_git_staging_failure_preserves_the_tool_failure_diagnostics(repo, tmp_path, monkeypatch):
    record_path(repo).write_text("{")
    original_git = shutil.which("git")
    commands = tmp_path / "commands"
    commands.mkdir()
    fake = commands / "git"
    fake.write_text(f"""#!/usr/bin/env python3
import os
import sys
if "diff-files" in sys.argv:
    print("simulated index read failure", file=sys.stderr)
    sys.exit(23)
os.execv({original_git!r}, [{original_git!r}, *sys.argv[1:]])
""")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", str(commands) + os.pathsep + os.environ["PATH"])

    result = refresh(repo)

    assert result.returncode != 0
    assert "local/live-picks.json" in result.stderr
    assert "simulated index read failure" in result.stderr
    assert "Traceback" not in result.stderr


def pi_record_path(repo):
    return repo / "local/live-picks-pi.json"


def save_pi(repo, values=PI_VALUES):
    pi_record_path(repo).write_text(json.dumps({PI: {"state": "set", "values": values}}) + "\n")


def pi_settings(repo):
    return json.loads((repo / PI).read_text())


def test_pi_capture_uses_its_own_record_and_keeps_the_old_record_unchanged(repo):
    saved_both(repo)
    original = record_path(repo).read_bytes()
    write_pi(repo, **PI_VALUES)

    result = picks(repo, "capture")

    assert result.returncode == 0, result.stderr
    assert json.loads(pi_record_path(repo).read_text()) == {PI: PI_SET}
    assert record_path(repo).read_bytes() == original
    assert PI not in record(repo)


def test_pi_later_pick_replaces_the_saved_model_pair(repo):
    save_pi(repo)
    write_pi(repo, defaultProvider="openai", defaultModel="gpt-6.1-sol")
    assert picks(repo, "capture").returncode == 0
    write_pi(repo)

    result = picks(repo, "restore")

    assert result.returncode == 0, result.stderr
    assert pi_settings(repo) == {**PI_BASE, "defaultProvider": "openai",
                                 "defaultModel": "gpt-6.1-sol", "defaultThinkingLevel": "high"}


@pytest.mark.parametrize("held, want", [
    ({"defaultThinkingLevel": "low"}, {**PI_VALUES, "defaultThinkingLevel": "low"}),
    ({"defaultProvider": "openai", "defaultModel": "gpt-6.1-sol"},
     {"defaultProvider": "openai", "defaultModel": "gpt-6.1-sol", "defaultThinkingLevel": "high"}),
])
def test_pi_restore_fills_only_the_absent_unit_then_capture_saves_both(repo, held, want):
    save_pi(repo)
    write_pi(repo, **held)

    assert picks(repo, "restore").returncode == 0
    assert pi_settings(repo) == {**PI_BASE, **want}
    assert picks(repo, "capture").returncode == 0
    assert json.loads(pi_record_path(repo).read_text()) == {PI: {"state": "set", "values": want}}


def test_pi_partial_model_pair_is_saved_as_is_and_never_completed(repo):
    save_pi(repo)
    write_pi(repo, defaultProvider="openai")

    result = picks(repo, "sync")

    assert result.returncode == 0, result.stderr
    assert pi_settings(repo) == {**PI_BASE, "defaultProvider": "openai", "defaultThinkingLevel": "high"}
    assert json.loads(pi_record_path(repo).read_text()) == {
        PI: {"state": "set", "values": {"defaultProvider": "openai", "defaultThinkingLevel": "high"}}}


def test_pi_all_absent_capture_keeps_the_saved_record_and_restore_recovers_it(repo):
    save_pi(repo)
    original = pi_record_path(repo).read_bytes()

    assert picks(repo, "capture").returncode == 0
    assert pi_record_path(repo).read_bytes() == original
    assert picks(repo, "restore").returncode == 0
    assert pi_settings(repo) == {**PI_BASE, **PI_VALUES}


def test_pi_forget_resets_both_units_and_survives_a_rewrite(repo):
    write_pi(repo, **PI_VALUES)
    assert picks(repo, "capture").returncode == 0

    result = picks(repo, "forget", PI)

    assert result.returncode == 0, result.stderr
    assert json.loads(pi_record_path(repo).read_text()) == {PI: {"state": "default"}}
    assert pi_settings(repo) == PI_BASE
    write_pi(repo, theme="light")
    git(repo, "checkout", "--", PI)
    assert picks(repo, "restore").returncode == 0
    assert pi_settings(repo) == PI_BASE
    assert status(repo) == ""


def test_pi_missing_record_restores_nothing(repo):
    before = (repo / PI).read_bytes()

    assert picks(repo, "restore").returncode == 0

    assert (repo / PI).read_bytes() == before
    assert not pi_record_path(repo).exists()


@pytest.mark.parametrize("operation", ["capture", "restore", "sync"])
@pytest.mark.parametrize("text", [
    "{", "[]", '{"other.json": {"state": "default"}}',
    '{"claude/settings.json": {"state": "default"}}',
    '{"pi/settings.json": {"state": "maybe"}}',
    '{"pi/settings.json": {"state": "set", "values": {"deviceId": "private"}}}',
    '{"pi/settings.json": {"state": "default", "values": {}}}',
])
def test_invalid_pi_record_is_refused_independently(repo, text, operation):
    saved_both(repo)
    write_claude(repo, model="sonnet")
    pi_record_path(repo).write_text(text)
    before = (repo / PI).read_bytes()

    result = picks(repo, operation)

    assert result.returncode != 0
    assert "local/live-picks-pi.json" in result.stderr
    assert pi_record_path(repo).read_text() == text
    assert (repo / PI).read_bytes() == before
    if operation in ("capture", "sync"):
        assert record(repo)[CLAUDE] == {"state": "set", "values": {"model": "sonnet"}}
    if operation in ("restore", "sync"):
        assert codex(repo)["model"] == "gpt-6.1-sol"


@pytest.mark.parametrize("operation", ["capture", "restore", "sync"])
def test_invalid_old_record_does_not_prevent_pi_preservation(repo, operation):
    record_path(repo).write_text("{")
    save_pi(repo)
    write_pi(repo, defaultThinkingLevel="low")

    result = picks(repo, operation)

    assert result.returncode != 0
    assert "local/live-picks.json" in result.stderr
    assert record_path(repo).read_text() == "{"
    if operation in ("capture", "sync"):
        assert json.loads(pi_record_path(repo).read_text())[PI]["values"] == {
            **PI_VALUES, "defaultThinkingLevel": "low"}
    if operation in ("restore", "sync"):
        assert pi_settings(repo) == {**PI_BASE, **PI_VALUES, "defaultThinkingLevel": "low"}


@pytest.mark.parametrize("changed", [CLAUDE, PI])
def test_capture_rewrites_only_the_record_whose_content_changed(repo, changed):
    write_claude(repo, model="opus")
    write_pi(repo, **PI_VALUES)
    assert picks(repo, "capture").returncode == 0
    paths = {CLAUDE: record_path(repo), PI: pi_record_path(repo)}
    before = {name: (path.stat().st_ino, path.stat().st_mtime_ns) for name, path in paths.items()}
    if changed == PI:
        write_pi(repo, **{**PI_VALUES, "defaultThinkingLevel": "low"})
    else:
        write_claude(repo, model="sonnet")

    assert picks(repo, "capture").returncode == 0

    for name, path in paths.items():
        assert ((path.stat().st_ino, path.stat().st_mtime_ns) != before[name]) == (name == changed)


def test_pi_ids_are_neither_captured_nor_restored_and_other_settings_survive(repo):
    write_pi(repo, **PI_VALUES, deviceId="device", trackingId="tracking")
    assert picks(repo, "capture").returncode == 0
    assert json.loads(pi_record_path(repo).read_text()) == {PI: PI_SET}
    write_pi(repo, theme="light", notice="café ▸")
    before = clean(repo, PI, (repo / PI).read_text())

    assert picks(repo, "restore").returncode == 0

    assert pi_settings(repo) == {**PI_BASE, **PI_VALUES, "theme": "light", "notice": "café ▸"}
    assert clean(repo, PI, (repo / PI).read_text()) == before


@pytest.mark.parametrize("groups", [
    {CLAUDE: (("model", "modelSettings"), ("effortLevel",)),
     PI: (("defaultProvider", "defaultModel"), ("defaultModel",))},
    {CLAUDE: (("model", "modelSettings"), ("effortLevel",)), PI: (("theme",),)},
    {CLAUDE: (("model", "modelSettings"), ("effortLevel", "effortLevel")),
     PI: (("defaultProvider", "defaultModel"), ("defaultThinkingLevel",))},
    {CLAUDE: (("model", "modelSettings"),),
     PI: (("defaultProvider", "defaultModel"), ("defaultThinkingLevel",))},
])
def test_json_groups_refuse_overlap_unfiltered_keys_and_missing_claude_keys(repo, groups):
    tool = repo / ".githooks/live-picks"
    source = tool.read_text()
    assignment = next((node for node in ast.parse(source).body if isinstance(node, ast.Assign)
                       and any(isinstance(target, ast.Name) and target.id == "JSON_GROUPS"
                               for target in node.targets)), None)
    if assignment:
        lines = source.splitlines(keepends=True)
        lines[assignment.lineno - 1:assignment.end_lineno] = [f"JSON_GROUPS = {groups!r}\n"]
        source = "".join(lines)
    else:
        source = source.replace("if sorted(sum(CLAUDE_GROUPS", f"JSON_GROUPS = {groups!r}\nif sorted(sum(CLAUDE_GROUPS")
    tool.write_text(source)

    result = picks(repo, "capture")

    assert result.returncode != 0
    assert "groups" in result.stderr.lower()
    assert "filter" in result.stderr.lower()
    assert not record_path(repo).exists()
    assert not pi_record_path(repo).exists()


@pytest.mark.parametrize("rewrite", ["merge", "switch", "checkout", "rebase"])
def test_pi_git_rewrites_restore_the_pick_without_tracking_it(repo, rewrite):
    git(repo, "switch", "-q", "-c", "side")
    write_pi(repo, theme="light")
    git(repo, "add", PI)
    git(repo, "commit", "-q", "-m", "side settings")
    git(repo, "switch", "-q", "main")
    if rewrite == "rebase":
        (repo / "u").write_text("main\n")
        git(repo, "add", "u")
        git(repo, "commit", "-q", "-m", "main")
    write_pi(repo, **PI_VALUES)
    assert picks(repo, "capture").returncode == 0
    git(repo, "add", PI)
    if rewrite == "checkout":
        write_pi(repo, theme="light", **PI_VALUES)
        result = git(repo, "checkout", "--", PI)
    else:
        result = git(repo, rewrite, "-q", "side")

    assert result.stderr == "" or rewrite == "rebase"
    assert pi_settings(repo) == {**PI_BASE, **PI_VALUES,
                                 "theme": "system" if rewrite == "checkout" else "light"}
    assert "defaultModel" not in git(repo, "show", "HEAD:" + PI).stdout
    assert status(repo) == ""


# Main before this change (after hq-61a47e); keep testing rollback after it lands.
PRE_PI_COMMIT = "6b434eb"


@pytest.fixture(scope="module")
def pre_pi_hooks():
    found = git(HOOKS.parent, "rev-parse", "--verify", "--quiet",
                f"{PRE_PI_COMMIT}^{{commit}}", check=False)
    if found.returncode == 1 and not found.stderr:
        pytest.skip(f"pre-pi commit {PRE_PI_COMMIT} is absent (shallow clone)")
    found.check_returncode()
    return {name: subprocess.run(
        ["git", "-C", str(HOOKS.parent), "show", f"{PRE_PI_COMMIT}:.githooks/{name}"],
        check=True, capture_output=True).stdout for name in HOOK_FILES}


def install_pre_pi_hooks(repo, pre_pi_hooks):
    for name, content in pre_pi_hooks.items():
        (repo / ".githooks" / name).write_bytes(content)


@contextlib.contextmanager
def owned_process(command):
    """Reap rollback commands through timeouts, assertions, and harness interrupts."""
    def interrupted(signum, frame):
        raise SystemExit(128 + signum)

    previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True, start_new_session=True) as run:
            try:
                yield run
            finally:
                # A finished leader can still leave descendants holding pipes or locks.
                try:
                    os.killpg(run.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
    finally:
        signal.signal(signal.SIGTERM, previous)


@pytest.mark.parametrize("stop", ["timeout", "sigint", "sigterm", "leader-exit"])
def test_rollback_process_cleanup_reaps_leader_and_stops_descendants(stop):
    import ctypes

    # Reuse the extension probe's subreaper pattern to own even a broken cleanup's orphans.
    libc = ctypes.CDLL(None, use_errno=True)
    previous = ctypes.c_int()
    assert libc.prctl(37, ctypes.byref(previous), 0, 0, 0) == 0
    assert libc.prctl(36, 1, 0, 0, 0) == 0
    descendant = """
import os, signal
signal.signal(signal.SIGTERM, signal.SIG_IGN)
print(os.getpid(), flush=True)
signal.pause()
"""
    launcher = """
import signal, subprocess, sys
child = subprocess.Popen([sys.executable, "-c", sys.argv[1]])
if sys.argv[2] != "leader-exit":
    signal.pause()
"""
    expected = {"timeout": subprocess.TimeoutExpired, "sigint": KeyboardInterrupt,
                "sigterm": SystemExit}
    run = child = None
    try:
        with pytest.raises(expected[stop]) if stop in expected else contextlib.nullcontext():
            with owned_process([sys.executable, "-c", launcher, descendant, stop]) as run:
                ready, _, _ = select.select([run.stdout], [], [], 10)
                assert ready, "descendant did not start"
                child = int(run.stdout.readline())
                if stop == "leader-exit":
                    assert run.wait(timeout=10) == 0
                elif stop == "timeout":
                    run.communicate(timeout=0.05)
                else:
                    os.kill(os.getpid(), {"sigint": signal.SIGINT,
                                          "sigterm": signal.SIGTERM}[stop])
        assert run.returncode is not None
        with pytest.raises(ChildProcessError):
            os.waitpid(run.pid, os.WNOHANG)
        deadline = time.monotonic() + 1
        reaped = 0
        while not reaped and time.monotonic() < deadline:
            reaped, _ = os.waitpid(child, os.WNOHANG)
            if not reaped:
                time.sleep(0.01)
        assert reaped == child, "descendant survived rollback command cleanup"
    finally:
        if run is not None:
            try:
                os.killpg(run.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            run.wait(timeout=10)
            # Reap by group even if startup failed before the descendant reported its pid.
            while True:
                try:
                    os.waitpid(-run.pid, 0)
                except ChildProcessError:
                    break
        assert libc.prctl(36, previous.value, 0, 0, 0) == 0


@pytest.mark.parametrize("command", [
    ("live-picks", "capture"), ("live-picks", "restore"),
    ("live-picks", "hook", "post-merge"), ("harness-state-refresh",),
])
def test_pinned_pre_pi_commands_leave_the_pi_record_untouched(repo, pre_pi_hooks, command):
    saved_both(repo)
    write_pi(repo, **PI_VALUES)
    with owned_process([str(repo / ".githooks/live-picks"), "capture"]) as captured:
        _, err = captured.communicate("", timeout=10)
        assert captured.returncode == 0, err
    before = pi_record_path(repo).read_bytes()
    install_pre_pi_hooks(repo, pre_pi_hooks)

    with owned_process([str(repo / ".githooks" / command[0]), *command[1:]]) as result:
        _, err = result.communicate("", timeout=10)
        assert result.returncode == 0, err
    assert pi_record_path(repo).read_bytes() == before
    assert PI not in record(repo)


def test_inflight_pi_capture_remains_safe_after_rollback(repo, pre_pi_hooks):
    saved_both(repo)
    save_pi(repo)
    write_claude(repo, model="opus")
    (repo / CODEX).write_text(PICK + BASE)
    write_pi(repo, defaultProvider="openai", defaultModel="gpt-6.1-sol",
             defaultThinkingLevel="medium")
    lock = repo / "local/harness-state.lock"
    lock.touch()
    before = {path: path.read_bytes() for path in (repo / "local").rglob("*")
              if path.is_file()}
    live_before = {name: (repo / name).read_bytes() for name in (CLAUDE, CODEX, PI)}
    # Load every definition first, then announce only a confirmed lock contention.
    runner = """
import fcntl, runpy, sys
sys.path.insert(0, sys.argv[1])
tool = runpy.run_path(sys.argv[1] + "/live-picks")
flock = fcntl.flock

def waiting(fd, operation):
    try:
        flock(fd, operation | fcntl.LOCK_NB)
    except BlockingIOError:
        print("loaded and blocked", flush=True)
        flock(fd, operation)
    else:
        raise AssertionError("capture did not contend for the host lock")

fcntl.flock = waiting
tool["main"](["live-picks", "capture"])
"""
    with lock.open("a") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        with owned_process([sys.executable, "-c", runner, str(repo / ".githooks")]) as run:
            ready, _, _ = select.select([run.stdout], [], [], 10)
            assert ready, "capture did not reach the host lock"
            assert run.stdout.readline() == "loaded and blocked\n"
            assert run.poll() is None
            install_pre_pi_hooks(repo, pre_pi_hooks)
            fcntl.flock(held, fcntl.LOCK_UN)
            _, err = run.communicate("", timeout=10)
            assert run.returncode == 0, err

    after = {path: path.read_bytes() for path in (repo / "local").rglob("*")
             if path.is_file()}
    assert set(after) == set(before)
    assert after.pop(pi_record_path(repo)) != before.pop(pi_record_path(repo))
    assert after == before
    assert json.loads(pi_record_path(repo).read_text()) == {PI: {"state": "set", "values": {
        "defaultProvider": "openai", "defaultModel": "gpt-6.1-sol",
        "defaultThinkingLevel": "medium"}}}
    assert {name: (repo / name).read_bytes() for name in live_before} == live_before

    with owned_process([str(repo / ".githooks/live-picks"), "capture"]) as result:
        _, err = result.communicate("", timeout=10)
        assert result.returncode == 0, err
    assert record(repo) == {CLAUDE: CLAUDE_SET, CODEX: CODEX_SET}
    assert PI not in record(repo)
