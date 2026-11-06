"""live-picks saves the model and effort picks in local/ and puts back what a git command dropped."""
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
CLAUDE = "harnesses/claude/settings.json"
CODEX = "harnesses/codex/config.toml"
PI = "harnesses/pi/settings.json"
AGY = "harnesses/agy/settings.json"
PI_BASE = {"lastChangelogVersion": "1.1.0", "theme": "system"}
PI_VALUES = {"defaultProvider": "anthropic", "defaultModel": "claude-opus-5-5",
             "defaultThinkingLevel": "high"}
PI_SET = {"state": "set", "values": PI_VALUES}
AGY_BASE = {"allowNonWorkspaceAccess": True, "permissions": {"allow": ["command(tasks)"]}}
AGY_VALUES = {"model": "Gemini 4 Argon (Medium)", "effort": "high",
              "effortByBase": {"Gemini 4 Argon": "high"}, "trustedWorkspaces": ["/work/a"]}
AGY_SET = {"state": "set", "values": AGY_VALUES}
BASE = "[features]\nhooks = true\n"
TUI = "[tui]\nx = 1\n"
PICK = 'model = "gpt-6.1-sol"\nmodel_reasoning_effort = "high"\n'
PICK_LINES = ['model = "gpt-6.1-sol"\n', 'model_reasoning_effort = "high"\n']
A = '[projects."/work/a"]\ntrust_level = "trusted"\n'


PROCESS_HOME = None


@pytest.fixture(scope="module", autouse=True)
def isolated_process_home(tmp_path_factory):
    global PROCESS_HOME
    PROCESS_HOME = tmp_path_factory.mktemp("live-picks-home")
    yield
    PROCESS_HOME = None


def child_env():
    assert PROCESS_HOME is not None
    return {"PATH": os.environ["PATH"], "HOME": str(PROCESS_HOME),
            "XDG_CONFIG_HOME": str(PROCESS_HOME / ".config"),
            "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
            "PYTHONDONTWRITEBYTECODE": "1"}


def git(repo, *args, check=True):
    return subprocess.run(["git", "-C", str(repo), *args], check=check, text=True,
                          capture_output=True, env=child_env())


def write_claude(repo, **settings):
    data = {"theme": "dark-ansi", **settings}
    (repo / CLAUDE).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def write_pi(repo, **settings):
    (repo / PI).write_text(json.dumps({**PI_BASE, **settings}, indent=2) + "\n")


def write_agy(repo, **settings):
    (repo / AGY).write_text(json.dumps({**AGY_BASE, **settings}, indent=2) + "\n")


@pytest.fixture
def repo(tmp_path, request, monkeypatch):
    """A main checkout shaped like this one: the filter, the hooks, both configs, local/."""
    historical = "pre_pi_hooks" in request.fixturenames
    if historical:
        # Keep pinned historical hooks and their layout authentic. These tests exercise
        # pick/manifest rollback; the separate layout rehearsal covers directory rollback.
        for name in ("CLAUDE", "CODEX", "PI", "AGY"):
            monkeypatch.setitem(globals(), name, globals()[name].removeprefix("harnesses/"))
    repo = tmp_path / "hq"
    (repo / ".githooks").mkdir(parents=True)
    for name in HOOK_FILES:
        shutil.copy2(HOOKS / name, repo / ".githooks" / name)
    shutil.copy2(HOOKS.parent / "harnesses.toml", repo / "harnesses.toml")
    for config in (CLAUDE, CODEX, PI, AGY):
        (repo / config).parent.mkdir(parents=True, exist_ok=True)
    (repo / "local" / "codex").mkdir(parents=True)
    (repo / ".gitattributes").write_text("harnesses/claude/settings*.json filter=harness-state\n"
                                         "harnesses/codex/config*.toml filter=harness-state\n"
                                         "harnesses/pi/settings*.json filter=harness-state\n"
                                         "harnesses/agy/settings*.json filter=harness-state\n")
    (repo / ".gitignore").write_text("local/\n__pycache__/\n")
    if historical:
        for path in [repo / "harnesses.toml", repo / ".gitattributes", *[repo / ".githooks" / n for n in HOOK_FILES]]:
            path.write_text(path.read_text().replace("harnesses/", ""))
    write_claude(repo)
    (repo / CODEX).write_text(BASE)
    write_pi(repo)
    write_agy(repo)
    git(tmp_path, "init", "-q", "-b", "main", str(repo))
    assert Path(git(repo, "rev-parse", "--show-toplevel").stdout.strip()) == repo.resolve()
    assert Path(git(repo, "rev-parse", "--absolute-git-dir").stdout.strip()).is_relative_to(repo.resolve())
    git(repo, "config", "filter.harness-state.clean", ".githooks/harness-state-clean %f")
    git(repo, "config", "filter.harness-state.required", "true")
    git(repo, "config", "filter.harness-state.smudge", "cat")
    git(repo, "config", "core.hooksPath", ".githooks")
    git(repo, "config", "user.email", "t@example.invalid")
    git(repo, "config", "user.name", "t")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def picks(repo, *args):
    """Run live-picks as the hooks do: by path, from another directory."""
    return subprocess.run([str(repo / ".githooks" / "live-picks"), *args], cwd=repo.parent,
                          text=True, capture_output=True, env=child_env())


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
                          input=text, check=True, text=True, capture_output=True, env=child_env()).stdout


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
    '{"harnesses/claude/settings.json": {"state": "maybe"}}',
    '{"harnesses/claude/settings.json": {"state": "set", "values": {"theme": "x"}}}',
    '{"harnesses/claude/settings.json": {"state": "default", "values": {}}}',
    '{"harnesses/codex/config.toml": {"state": "set", "lines": ["theme = 1\\n"]}}',
    '{"harnesses/codex/config.toml": {"state": "set", "lines": ["model = \\"x\\""]}}',
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
    assert "harnesses/claude/settings.json does not parse" in result.stderr
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
    result = picks(repo, "forget", "harnesses/claude/settings.work.json")

    assert result.returncode != 0
    assert "forget takes" in result.stderr


def test_concurrent_syncs_of_both_tools_keep_trust_and_the_pick(repo):
    (repo / "local" / "codex" / "trust.toml").write_text(A)
    save(repo, **{CODEX: CODEX_SET})
    tools = ("codex-trust", "live-picks") * 6
    runs = [subprocess.Popen([str(repo / ".githooks" / tool), "sync"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=child_env())
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
    assert "harnesses/codex/config.toml is missing" in result.stderr


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
                            input="old new\n", text=True, capture_output=True, env=child_env())

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
                          text=True, capture_output=True, env=child_env())


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
    assert "harnesses/claude/settings.json does not parse" in result.stderr
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
    '{"harnesses/claude/settings.json": {"state": "default"}}',
    '{"harnesses/pi/settings.json": {"state": "maybe"}}',
    '{"harnesses/pi/settings.json": {"state": "set", "values": {"deviceId": "private"}}}',
    '{"harnesses/pi/settings.json": {"state": "default", "values": {}}}',
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


def isolated_home(repo, tmp_path):
    """A HOME the test owns, after checking git resolves the scratch repo and not another."""
    home = tmp_path / "isolated-home"
    home.mkdir(exist_ok=True)
    top = isolated_git(repo, home, "rev-parse", "--show-toplevel").stdout.strip()
    git_dir = isolated_git(repo, home, "rev-parse", "--absolute-git-dir").stdout.strip()
    assert Path(top).resolve() == repo.resolve()
    assert repo.resolve() in Path(git_dir).resolve().parents
    return home


def edit_manifest(repo, old, new):
    path = repo / "harnesses.toml"
    text = path.read_text()
    assert text.count(old) == 1, old
    path.write_text(text.replace(old, new))


CLAUDE_UNITS = 'pick_units = [["model", "modelSettings"], ["effortLevel"]]'
PI_UNITS = 'pick_units = [["defaultProvider", "defaultModel"], ["defaultThinkingLevel"]]'
AGY_UNITS = ('pick_units = [["model"], ["effort", "effortByBase"], ["trustedWorkspaces"], '
             '["seasonalThemesOptIn"]]')
CODEX_UNITS = 'pick_units = [["model", "model_reasoning_effort"]]'


@pytest.mark.parametrize("old, new", [
    (PI_UNITS, 'pick_units = [["defaultProvider", "defaultModel"], ["defaultModel", "defaultThinkingLevel"]]'),
    (PI_UNITS, 'pick_units = [["defaultProvider", "defaultModel"], ["defaultThinkingLevel"], ["theme"]]'),
    (CLAUDE_UNITS, 'pick_units = [["model", "modelSettings"]]'),
    (AGY_UNITS, 'pick_units = [["model"], ["effort", "effortByBase"], ["trustedWorkspaces"]]'),
    (CODEX_UNITS, 'pick_units = [["model"]]'),
], ids=["pi-overlap", "pi-unfiltered", "claude-missing", "agy-missing", "codex-missing"])
def test_manifest_partition_and_overlap_violations_are_refused(repo, tmp_path, old, new):
    home = isolated_home(repo, tmp_path)
    write_claude(repo, model="opus")
    (repo / CODEX).write_text(PICK + BASE)
    write_pi(repo, **PI_VALUES)
    write_agy(repo, **AGY_VALUES)
    edit_manifest(repo, old, new)

    result = isolated_picks(repo, home, "capture")

    assert result.returncode != 0
    assert "live-picks: " in result.stderr
    assert "pick_units" in result.stderr
    assert "Traceback" not in result.stderr
    assert sorted((repo / "local").glob("live-picks*.json")) == []


def damage_manifest(path, damage):
    if damage == "missing":
        path.unlink()
    elif damage == "truncated":
        path.write_text(path.read_text()[:path.read_text().index("[harnesses.agy.live_state]") + 18])
    elif damage == "format-list":
        text = path.read_text()
        assert 'format = "json"' in text
        path.write_text(text.replace('format = "json"', 'format = ["json"]', 1))
    else:
        path.write_bytes(b"schema = 1\n\xff\xfe\n")


@pytest.mark.parametrize("damage", ["truncated", "non-utf8", "missing", "format-list"])
def test_broken_manifest_hook_exits_zero_with_retry_while_cli_fails_and_bad_args_print_usage(
        repo, tmp_path, damage):
    home = isolated_home(repo, tmp_path)
    isolated_git(repo, home, "switch", "-q", "-c", "side")
    (repo / "u").write_text("side\n")
    isolated_git(repo, home, "add", "u")
    isolated_git(repo, home, "commit", "-q", "-m", "side")
    isolated_git(repo, home, "switch", "-q", "main")
    other = tmp_path / "other"
    isolated_git(repo, home, "worktree", "add", "-q", "-b", "mine", str(other), "main")
    # Age every tracked file and refresh the index while the manifest is valid, so the
    # switch below finds each filtered config stat-clean and only the hooks read the
    # broken manifest, never the clean filter.
    past = time.time() - 60
    for name in isolated_git(repo, home, "ls-files").stdout.split():
        os.utime(repo / name, (past, past))
    isolated_git(repo, home, "update-index", "-q", "--really-refresh")
    assert isolated_git(repo, home, "diff-files", "--name-only").stdout == ""
    damage_manifest(repo / "harnesses.toml", damage)
    damage_manifest(other / "harnesses.toml", damage)

    hook = isolated_picks(repo, home, "hook", "post-merge")
    switched = isolated_git(repo, home, "switch", "-q", "side", check=False)
    linked = isolated_picks(other, home, "hook", "post-merge")
    cli = {args: isolated_picks(repo, home, *args)
           for args in (("capture",), ("sync",), ("forget", CLAUDE))}
    bogus = isolated_picks(repo, home, "bogus")

    for result in (hook, switched):
        assert result.returncode == 0, result.stderr
        assert "live-picks: " in result.stderr
        assert "the next turn end retries" in result.stderr
        assert "Traceback" not in result.stderr
    assert isolated_git(repo, home, "branch", "--show-current").stdout.strip() == "side"
    assert (linked.returncode, linked.stderr) == (0, "")
    for args, result in cli.items():
        assert result.returncode != 0, args
        assert "live-picks: " in result.stderr
        assert "Traceback" not in result.stderr
    assert bogus.returncode != 0
    assert "usage: live-picks" in bogus.stderr
    assert "Traceback" not in bogus.stderr
    assert sorted((repo / "local").glob("live-picks*.json")) == []


EXTRA = "extra/config.toml"
EXTRA_RECORD = "local/live-picks-extra.json"
EXTRA_SPEC = """
[harnesses.extra.live_state]
config = "extra/config.toml"
filter_glob = "extra/config*.toml"
format = "toml"
clean_keys = [{ table = "", keys = ["model", "effort", "tier", "install_id"] }]
unrestored_keys = ["install_id"]
picks_record = "local/live-picks-extra.json"
pick_units = [["model"], ["effort", "tier"]]
"""
EXTRA_BASE = '# tracked comment\nname = "x"\n\n[tables]\nk = 1  # kept\n'


def add_extra_harness(repo, home):
    """A second TOML harness with two picker units and an installation id it never restores."""
    with (repo / "harnesses.toml").open("a") as manifest:
        manifest.write(EXTRA_SPEC)
    with (repo / ".gitattributes").open("a") as attributes:
        attributes.write("extra/config*.toml filter=harness-state\n")
    (repo / "extra").mkdir()
    (repo / EXTRA).write_text(EXTRA_BASE)
    isolated_git(repo, home, "add", "harnesses.toml", ".gitattributes", EXTRA)
    isolated_git(repo, home, "commit", "-q", "-m", "extra harness")


def extra_record(repo):
    path = repo / EXTRA_RECORD
    return json.loads(path.read_text()) if path.exists() else None


def save_extra(repo, lines):
    (repo / EXTRA_RECORD).write_text(json.dumps({EXTRA: {"state": "set", "lines": lines}}) + "\n")


def test_multi_unit_toml_merges_units_in_declaration_order_and_preserves_unrestored_keys_on_forget(
        repo, tmp_path):
    home = isolated_home(repo, tmp_path)
    add_extra_harness(repo, home)
    save_extra(repo, ['model = "m1"\n', 'effort = "low"\n', 'tier = "t1"\n'])

    # A pick of the second unit keeps the first unit's saved value, in declaration order.
    (repo / EXTRA).write_text('effort = "high"\ntier = "t2"\n' + EXTRA_BASE)
    result = isolated_picks(repo, home, "capture")
    assert result.returncode == 0, result.stderr
    assert extra_record(repo) == {EXTRA: {"state": "set", "lines": [
        'model = "m1"\n', 'effort = "high"\n', 'tier = "t2"\n']}}

    # Units held in reverse order in the live file are still saved in declaration order.
    (repo / EXTRA).write_text('effort = "e3"\ntier = "t3"\nmodel = "m3"\ninstall_id = "abc"\n'
                              + EXTRA_BASE)
    result = isolated_picks(repo, home, "capture")
    assert result.returncode == 0, result.stderr
    assert extra_record(repo) == {EXTRA: {"state": "set", "lines": [
        'model = "m3"\n', 'effort = "e3"\n', 'tier = "t3"\n']}}
    assert record(repo) is None

    # restore fills only the unit the file holds none of, keeping comments and tables.
    held = 'tier = "t9"\n' + EXTRA_BASE
    (repo / EXTRA).write_text(held)
    result = isolated_picks(repo, home, "restore")
    assert result.returncode == 0, result.stderr
    assert (repo / EXTRA).read_text() == 'model = "m3"\n' + held
    held = 'model = "m9"\n' + EXTRA_BASE
    (repo / EXTRA).write_text(held)
    result = isolated_picks(repo, home, "restore")
    assert result.returncode == 0, result.stderr
    assert (repo / EXTRA).read_text() == 'effort = "e3"\ntier = "t3"\n' + held

    # forget removes every pick unit and keeps the installation id it never restores.
    (repo / EXTRA).write_text('model = "m3"\ninstall_id = "abc"\neffort = "e3"\ntier = "t3"\n'
                              + EXTRA_BASE)
    result = isolated_picks(repo, home, "forget", EXTRA)
    assert result.returncode == 0, result.stderr
    assert (repo / EXTRA).read_text() == 'install_id = "abc"\n' + EXTRA_BASE
    assert extra_record(repo) == {EXTRA: {"state": "default"}}
    result = isolated_picks(repo, home, "restore")
    assert result.returncode == 0, result.stderr
    assert (repo / EXTRA).read_text() == 'install_id = "abc"\n' + EXTRA_BASE


@pytest.mark.parametrize("name", [CODEX, EXTRA])
@pytest.mark.parametrize("bad, refusal", [
    ('model = "a"\nmodel = "b"\n', "does not parse"),
    ('"model" = "x"\n', "one-line keys"),
], ids=["duplicate", "quoted"])
def test_toml_duplicate_or_quoted_key_mismatch_is_refused(repo, tmp_path, name, bad, refusal):
    home = isolated_home(repo, tmp_path)
    add_extra_harness(repo, home)
    saved_both(repo)
    save_extra(repo, ['model = "m1"\n', 'effort = "low"\n', 'tier = "t1"\n'])
    before_records = {path: path.read_bytes() for path in (record_path(repo), repo / EXTRA_RECORD)}
    write_claude(repo, model="sonnet")
    write_pi(repo, **PI_VALUES)
    base = BASE if name == CODEX else EXTRA_BASE
    (repo / name).write_text(bad + base)
    other = EXTRA if name == CODEX else CODEX
    (repo / other).write_text(BASE if other == CODEX else EXTRA_BASE)

    captured = isolated_picks(repo, home, "capture")
    restored = isolated_picks(repo, home, "restore")

    for result in (captured, restored):
        assert result.returncode != 0
        assert f"{name}" in result.stderr and refusal in result.stderr
        assert "Traceback" not in result.stderr
    assert (repo / name).read_text() == bad + base
    assert record(repo)[CLAUDE] == {"state": "set", "values": {"model": "sonnet"}}
    assert json.loads(pi_record_path(repo).read_text()) == {PI: PI_SET}
    own = record_path(repo) if name == CODEX else repo / EXTRA_RECORD
    assert json.loads(own.read_text())[name] == json.loads(before_records[own])[name]
    if other == CODEX:
        assert codex(repo)["model"] == "gpt-6.1-sol"
    else:
        assert (repo / EXTRA).read_text().startswith('model = "m1"\n')


@pytest.mark.parametrize("lines", [
    ['model = "a"\n', 'model = "b"\n'],
    ['"model" = "x"\n'],
    ['install_id = "abc"\n'],
], ids=["duplicate", "quoted", "unrestored"])
def test_a_multi_unit_toml_record_with_bad_lines_is_refused_and_left_alone(repo, tmp_path, lines):
    home = isolated_home(repo, tmp_path)
    add_extra_harness(repo, home)
    save_extra(repo, lines)
    text = (repo / EXTRA_RECORD).read_text()

    result = isolated_picks(repo, home, "sync")

    assert result.returncode != 0
    assert f"live-picks: {EXTRA_RECORD}" in result.stderr
    assert (repo / EXTRA_RECORD).read_text() == text
    assert (repo / EXTRA).read_text() == EXTRA_BASE


CLEAN_ONLY = "cleanonly/settings.json"
CLEAN_ONLY_SPEC = """
[harnesses.cleanonly.live_state]
config = "cleanonly/settings.json"
filter_glob = "cleanonly/settings*.json"
format = "json"
clean_keys = ["token"]
"""


def test_clean_only_live_state_is_skipped_by_live_picks_sync_and_refused_by_forget(repo, tmp_path):
    home = isolated_home(repo, tmp_path)
    with (repo / "harnesses.toml").open("a") as manifest:
        manifest.write(CLEAN_ONLY_SPEC)
    with (repo / ".gitattributes").open("a") as attributes:
        attributes.write("cleanonly/settings*.json filter=harness-state\n")
    (repo / "cleanonly").mkdir()
    (repo / CLEAN_ONLY).write_text('{"token": "t", "theme": "x"}\n')
    write_claude(repo, model="opus")

    synced = isolated_picks(repo, home, "sync")
    forgot = isolated_picks(repo, home, "forget", CLEAN_ONLY)
    usage = isolated_picks(repo, home, "bogus")

    assert synced.returncode == 0, synced.stderr
    assert record(repo) == {CLAUDE: CLAUDE_SET}
    assert sorted(path.name for path in (repo / "local").glob("live-picks*.json")) == ["live-picks.json"]
    assert forgot.returncode != 0
    assert "not a file live-picks owns" in forgot.stderr
    assert "Traceback" not in forgot.stderr
    assert (repo / CLEAN_ONLY).read_text() == '{"token": "t", "theme": "x"}\n'
    assert CLEAN_ONLY not in usage.stderr
    assert CLAUDE in usage.stderr


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
        check=True, capture_output=True, env=child_env()).stdout for name in HOOK_FILES}


def pinned_blob(scratch, path):
    """PRE_PI_COMMIT's blob of path, read from this checkout by git with an environment
    built key by key: no inherited GIT_* variable, a HOME and global config under scratch."""
    home = scratch / "pinned-read-home"
    home.mkdir(exist_ok=True)
    (home / ".gitconfig").touch()
    env = {"PATH": os.environ["PATH"], "HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config"),
           "GIT_CONFIG_GLOBAL": str(home / ".gitconfig"), "GIT_CONFIG_NOSYSTEM": "1"}
    return subprocess.run(["git", "-C", str(HOOKS.parent), "show", f"{PRE_PI_COMMIT}:{path}"],
                          env=env, check=True, capture_output=True).stdout


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
                              stderr=subprocess.PIPE, text=True, start_new_session=True, env=child_env()) as run:
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
    # A rollback brings back the pinned commit's .gitattributes with its hooks: under the
    # required filter, the pinned clean filter refuses the agy path it predates.
    (repo / ".gitattributes").write_bytes(pinned_blob(repo.parent, ".gitattributes"))

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
            # A checkout of the pre-manifest commit replaces the hooks and deletes
            # harnesses.toml: the waiter must have read the manifest before the lock.
            install_pre_pi_hooks(repo, pre_pi_hooks)
            (repo / "harnesses.toml").unlink()
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


def test_single_unit_codex_record_bytes_match_pinned_6b434eb_and_rollback_works_without_manifest(
        repo, tmp_path, pre_pi_hooks):
    home = isolated_home(repo, tmp_path)
    write_claude(repo, model="opus", effortLevel="high")
    (repo / CODEX).write_text(PICK + BASE)
    captured = isolated_picks(repo, home, "capture")
    assert captured.returncode == 0, captured.stderr
    current = record_path(repo).read_bytes()
    assert current == (json.dumps({CLAUDE: {"state": "set", "values": {
        "model": "opus", "effortLevel": "high"}}, CODEX: CODEX_SET}, indent=2) + "\n").encode()
    (repo / "harnesses.toml").unlink()
    install_pre_pi_hooks(repo, pre_pi_hooks)

    # The pinned hooks keep the current record as it is and write the same bytes afresh.
    kept = isolated_picks(repo, home, "capture")
    assert kept.returncode == 0, kept.stderr
    assert record_path(repo).read_bytes() == current
    record_path(repo).unlink()
    rewritten = isolated_picks(repo, home, "capture")
    assert rewritten.returncode == 0, rewritten.stderr
    assert record_path(repo).read_bytes() == current
    write_claude(repo)
    (repo / CODEX).write_text(BASE)
    restored = isolated_picks(repo, home, "restore")

    assert restored.returncode == 0, restored.stderr
    assert record_path(repo).read_bytes() == current
    assert claude(repo) == {"theme": "dark-ansi", "model": "opus", "effortLevel": "high"}
    assert (repo / CODEX).read_text() == PICK + BASE


def agy_record_path(repo):
    return repo / "local/live-picks-agy.json"


def save_agy(repo, values=AGY_VALUES):
    agy_record_path(repo).write_text(json.dumps({AGY: {"state": "set", "values": values}}) + "\n")


def agy_settings(repo):
    return json.loads((repo / AGY).read_text())


def test_agy_capture_uses_its_own_record_and_keeps_other_records_unchanged(repo):
    saved_both(repo)
    save_pi(repo)
    original_main = record_path(repo).read_bytes()
    original_pi = pi_record_path(repo).read_bytes()
    write_agy(repo, **AGY_VALUES)

    result = picks(repo, "capture")

    assert result.returncode == 0, result.stderr
    assert json.loads(agy_record_path(repo).read_text()) == {AGY: AGY_SET}
    assert record_path(repo).read_bytes() == original_main
    assert pi_record_path(repo).read_bytes() == original_pi
    assert AGY not in record(repo)


@pytest.mark.parametrize("held, want", [
    ({"model": "Claude Sonnet 4.6"}, {**AGY_VALUES, "model": "Claude Sonnet 4.6"}),
    ({"effort": "low", "effortByBase": {"Gemini 4 Argon": "low"}},
     {**AGY_VALUES, "effort": "low", "effortByBase": {"Gemini 4 Argon": "low"}}),
    ({"trustedWorkspaces": ["/work/a", "/work/b"]},
     {**AGY_VALUES, "trustedWorkspaces": ["/work/a", "/work/b"]}),
])
def test_agy_restore_fills_only_the_absent_unit_then_capture_saves_all(repo, held, want):
    save_agy(repo)
    write_agy(repo, **held)

    assert picks(repo, "restore").returncode == 0
    assert agy_settings(repo) == {**AGY_BASE, **want}
    assert picks(repo, "capture").returncode == 0
    assert json.loads(agy_record_path(repo).read_text()) == {AGY: {"state": "set", "values": want}}


def test_agy_forget_resets_all_units_and_survives_a_rewrite(repo):
    write_agy(repo, **AGY_VALUES)
    assert picks(repo, "capture").returncode == 0

    result = picks(repo, "forget", AGY)

    assert result.returncode == 0, result.stderr
    assert json.loads(agy_record_path(repo).read_text()) == {AGY: {"state": "default"}}
    assert agy_settings(repo) == AGY_BASE
    write_agy(repo, allowNonWorkspaceAccess=False)
    git(repo, "checkout", "--", AGY)
    assert picks(repo, "restore").returncode == 0
    assert agy_settings(repo) == AGY_BASE
    assert status(repo) == ""


@pytest.mark.parametrize("rewrite", ["merge", "switch", "checkout", "rebase"])
def test_agy_git_rewrites_restore_the_pick_without_tracking_it(repo, rewrite):
    git(repo, "switch", "-q", "-c", "side")
    write_agy(repo, allowNonWorkspaceAccess=False)
    git(repo, "add", AGY)
    git(repo, "commit", "-q", "-m", "side settings")
    git(repo, "switch", "-q", "main")
    if rewrite == "rebase":
        (repo / "u").write_text("main\n")
        git(repo, "add", "u")
        git(repo, "commit", "-q", "-m", "main")
    write_agy(repo, **AGY_VALUES)
    assert picks(repo, "capture").returncode == 0
    git(repo, "add", AGY)
    if rewrite == "checkout":
        write_agy(repo, allowNonWorkspaceAccess=False, **AGY_VALUES)
        result = git(repo, "checkout", "--", AGY)
    else:
        result = git(repo, rewrite, "-q", "side")

    assert result.stderr == "" or rewrite == "rebase"
    assert agy_settings(repo) == {**AGY_BASE, **AGY_VALUES,
                                  "allowNonWorkspaceAccess": True if rewrite == "checkout" else False}
    assert "trustedWorkspaces" not in git(repo, "show", "HEAD:" + AGY).stdout
    assert "model" not in git(repo, "show", "HEAD:" + AGY).stdout
    assert status(repo) == ""


@pytest.mark.parametrize("command", [
    ("live-picks", "capture"), ("live-picks", "restore"),
    ("live-picks", "hook", "post-merge"), ("harness-state-refresh",),
])
def test_pinned_pre_pi_commands_leave_the_agy_record_untouched(repo, pre_pi_hooks, command):
    saved_both(repo)
    write_agy(repo, **AGY_VALUES)
    with owned_process([str(repo / ".githooks/live-picks"), "capture"]) as captured:
        _, err = captured.communicate("", timeout=10)
        assert captured.returncode == 0, err
    before = agy_record_path(repo).read_bytes()
    install_pre_pi_hooks(repo, pre_pi_hooks)

    with owned_process([str(repo / ".githooks" / command[0]), *command[1:]]) as result:
        _, err = result.communicate("", timeout=10)
        assert result.returncode == 0, err
    assert agy_record_path(repo).read_bytes() == before
    assert AGY not in record(repo)


def agy_env(home):
    return {
        "PATH": f"{home / '.test-bin'}:{os.environ['PATH']}",
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_STATE_HOME": str(home / ".local/state"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def isolated_git(repo, home, *args, check=True):
    return subprocess.run(["git", "-C", str(repo), *args], env=agy_env(home), check=check,
                          text=True, capture_output=True)


def isolated_picks(repo, home, *args):
    return subprocess.run([str(repo / ".githooks/live-picks"), *args], cwd=repo.parent,
                          env=agy_env(home), text=True, capture_output=True)


def isolated_refresh(repo, home):
    return subprocess.run([str(repo / ".githooks/harness-state-refresh")], cwd=repo.parent,
                          env=agy_env(home), input="", text=True, capture_output=True)


def anchor_agy_home(repo, tmp_path):
    home = tmp_path / "agy-home"
    (home / ".gemini/antigravity-cli").mkdir(parents=True)
    (home / ".gemini/config").mkdir(parents=True)
    assert Path(isolated_git(repo, home, "rev-parse", "--show-toplevel").stdout.strip()).resolve() == repo.resolve()
    assert repo.resolve() in Path(isolated_git(repo, home, "rev-parse", "--absolute-git-dir").stdout.strip()).resolve().parents
    hooks = repo / "harnesses/agy/hooks.json"
    if not hooks.exists():
        hooks.write_text("{}\n")
        isolated_git(repo, home, "add", "harnesses/agy/hooks.json")
        isolated_git(repo, home, "commit", "-q", "-m", "track agy hooks")
    (home / ".gemini/config/hooks.json").symlink_to(hooks)
    link = home / ".gemini/antigravity-cli/settings.json"
    link.symlink_to(repo / AGY)
    return home, link


def atomic_agy_save(link, data):
    tmp = link.with_name(".settings.json.agy-tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    tmp.chmod(0o600)
    os.replace(tmp, link)


def test_agy_atomic_replace_is_adopted_and_relinked_on_refresh(repo, tmp_path):
    home, link = anchor_agy_home(repo, tmp_path)
    save_agy(repo)
    atomic_agy_save(link, {
        **AGY_BASE,
        "model": "Gemini 4 Argon (High)",
        "trustedWorkspaces": ["/work/a", "/work/b"],
    })
    assert not link.is_symlink()

    result = isolated_refresh(repo, home)

    assert result.returncode == 0, result.stderr
    assert link.is_symlink()
    assert link.resolve() == (repo / AGY).resolve()
    want_picks = {
        **AGY_VALUES,
        "model": "Gemini 4 Argon (High)",
        "trustedWorkspaces": ["/work/a", "/work/b"],
    }
    assert agy_settings(repo) == {**AGY_BASE, **want_picks}
    assert json.loads(agy_record_path(repo).read_text()) == {AGY: {"state": "set", "values": want_picks}}
    assert isolated_git(repo, home, "status", "--porcelain").stdout == ""
    assert isolated_git(repo, home, "diff", "--cached", "--quiet", check=False).returncode == 0


def test_agy_atomic_replace_preserves_non_pick_config_change_unstaged(repo, tmp_path):
    home, link = anchor_agy_home(repo, tmp_path)
    atomic_agy_save(link, {
        **AGY_BASE,
        "queuedMessages": "send-immediately",
        "model": "Gemini 4 Argon (High)",
        "trustedWorkspaces": ["/work/a"],
    })

    result = isolated_refresh(repo, home)

    assert result.returncode == 0, result.stderr
    assert link.is_symlink() and link.resolve() == (repo / AGY).resolve()
    assert agy_settings(repo) == {
        **AGY_BASE,
        "queuedMessages": "send-immediately",
        "model": "Gemini 4 Argon (High)",
        "trustedWorkspaces": ["/work/a"],
    }
    assert json.loads(agy_record_path(repo).read_text()) == {
        AGY: {"state": "set", "values": {"model": "Gemini 4 Argon (High)", "trustedWorkspaces": ["/work/a"]}}
    }
    assert isolated_git(repo, home, "status", "--porcelain").stdout == f" M {AGY}\n"
    diff = isolated_git(repo, home, "diff", "--", AGY).stdout
    assert '"queuedMessages": "send-immediately"' in diff
    assert '"model"' not in diff
    assert isolated_git(repo, home, "diff", "--cached", "--quiet", check=False).returncode == 0


def test_agy_detached_capture_while_index_locked_touches_only_record_until_unlocked(repo, tmp_path):
    home, link = anchor_agy_home(repo, tmp_path)
    repo_before = (repo / AGY).read_bytes()
    before_tree = isolated_git(repo, home, "write-tree").stdout
    atomic_agy_save(link, {
        **AGY_BASE,
        "model": "Gemini 4 Argon (High)",
        "trustedWorkspaces": ["/work/a"],
    })
    lock = Path(isolated_git(repo, home, "rev-parse", "--path-format=absolute", "--git-path", "index.lock").stdout.strip())
    lock.write_text("")

    locked_run = isolated_refresh(repo, home)

    assert locked_run.returncode == 0, locked_run.stderr
    assert json.loads(agy_record_path(repo).read_text()) == {
        AGY: {"state": "set", "values": {"model": "Gemini 4 Argon (High)", "trustedWorkspaces": ["/work/a"]}}
    }
    assert (repo / AGY).read_bytes() == repo_before
    assert not link.is_symlink()
    lock.unlink()
    assert isolated_git(repo, home, "write-tree").stdout == before_tree

    unlocked_run = isolated_refresh(repo, home)

    assert unlocked_run.returncode == 0, unlocked_run.stderr
    assert link.is_symlink() and link.resolve() == (repo / AGY).resolve()
    assert agy_settings(repo) == {
        **AGY_BASE,
        "model": "Gemini 4 Argon (High)",
        "trustedWorkspaces": ["/work/a"],
    }
    assert isolated_git(repo, home, "status", "--porcelain").stdout == ""


@pytest.mark.parametrize("rewrite", ["merge", "switch", "checkout", "rebase", "reset"])
def test_agy_git_rewrites_adopt_detached_picks_onto_checked_out_settings_and_relink(repo, tmp_path, rewrite):
    home, link = anchor_agy_home(repo, tmp_path)
    isolated_git(repo, home, "switch", "-q", "-c", "side")
    write_agy(repo, allowNonWorkspaceAccess=False)
    isolated_git(repo, home, "add", AGY)
    isolated_git(repo, home, "commit", "-q", "-m", "side settings")
    isolated_git(repo, home, "switch", "-q", "main")
    if rewrite == "rebase":
        (repo / "u").write_text("main\n")
        isolated_git(repo, home, "add", "u")
        isolated_git(repo, home, "commit", "-q", "-m", "main")
    detached_picks = {
        "model": "Gemini 4 Argon (High)",
        "effort": "high",
        "effortByBase": {"Gemini 4 Argon": "high"},
        "trustedWorkspaces": ["/work/a", "/work/c"],
    }
    atomic_agy_save(link, {**AGY_BASE, **detached_picks})
    if rewrite == "reset":
        old_ns = (repo / AGY).stat().st_mtime_ns - 1_000_000_000
        os.utime(link, ns=(old_ns, old_ns))
        isolated_git(repo, home, "reset", "-q", "--hard", "side")
        result = isolated_refresh(repo, home)
        assert result.returncode == 0, result.stderr
    elif rewrite == "checkout":
        write_agy(repo, allowNonWorkspaceAccess=False)
        result = isolated_git(repo, home, "checkout", "--", AGY)
        assert result.stderr == ""
    else:
        result = isolated_git(repo, home, rewrite, "-q", "side")
        assert result.stderr == "" or rewrite == "rebase"

    assert link.is_symlink() and link.resolve() == (repo / AGY).resolve()
    want_allow = True if rewrite == "checkout" else False
    assert agy_settings(repo) == {**AGY_BASE, **detached_picks, "allowNonWorkspaceAccess": want_allow}
    assert json.loads(agy_record_path(repo).read_text()) == {AGY: {"state": "set", "values": detached_picks}}
    assert isolated_git(repo, home, "status", "--porcelain").stdout == ""


def test_agy_git_hooks_not_rewriting_agy_preserve_detached_non_pick_edits(repo, tmp_path):
    home, link = anchor_agy_home(repo, tmp_path)
    isolated_git(repo, home, "switch", "-q", "-c", "other-only")
    (repo / "other.txt").write_text("other\n")
    isolated_git(repo, home, "add", "other.txt")
    isolated_git(repo, home, "commit", "-q", "-m", "touch other file only")
    isolated_git(repo, home, "switch", "-q", "main")

    save_agy(repo)
    assert isolated_refresh(repo, home).returncode == 0
    atomic_agy_save(link, {
        **AGY_BASE,
        "queuedMessages": "send-immediately",
        **AGY_VALUES,
        "model": "Gemini 4 Argon (High)",
    })

    switched = isolated_git(repo, home, "switch", "-q", "-c", "feature")

    assert switched.returncode == 0, switched.stderr
    assert link.is_symlink() and link.resolve() == (repo / AGY).resolve()
    assert agy_settings(repo) == {
        **AGY_BASE,
        "queuedMessages": "send-immediately",
        **AGY_VALUES,
        "model": "Gemini 4 Argon (High)",
    }
    assert isolated_git(repo, home, "status", "--porcelain", "--", AGY).stdout == f" M {AGY}\n"

    isolated_git(repo, home, "checkout", "--", AGY)
    isolated_git(repo, home, "switch", "-q", "main")
    atomic_agy_save(link, {
        **AGY_BASE,
        "permissions": {"allow": ["Bash(just test)"], "deny": []},
        **AGY_VALUES,
    })

    merged = isolated_git(repo, home, "merge", "-q", "--no-ff", "other-only", "-m", "merge other")

    assert merged.returncode == 0, merged.stderr
    assert link.is_symlink() and link.resolve() == (repo / AGY).resolve()
    assert agy_settings(repo) == {
        **AGY_BASE,
        "permissions": {"allow": ["Bash(just test)"], "deny": []},
        **AGY_VALUES,
    }
    assert isolated_git(repo, home, "status", "--porcelain", "--", AGY).stdout == f" M {AGY}\n"

    isolated_git(repo, home, "checkout", "--", AGY)
    assert isolated_picks(repo, home, "forget", AGY).returncode == 0
    assert isolated_refresh(repo, home).returncode == 0
    old_ns = (repo / AGY).stat().st_mtime_ns - 1_000_000_000
    os.utime(repo / AGY, ns=(old_ns, old_ns))
    atomic_agy_save(link, {
        **AGY_BASE,
        "queuedMessages": "send-immediately",
    })

    switched_empty = isolated_git(repo, home, "switch", "-q", "-c", "no-picks-feature")

    assert switched_empty.returncode == 0, switched_empty.stderr
    assert link.is_symlink() and link.resolve() == (repo / AGY).resolve()
    assert agy_settings(repo) == {
        **AGY_BASE,
        "queuedMessages": "send-immediately",
    }
    assert isolated_git(repo, home, "status", "--porcelain", "--", AGY).stdout == f" M {AGY}\n"


def test_agy_forget_adopts_non_pick_settings_clears_picks_and_relinks(repo, tmp_path):
    home, link = anchor_agy_home(repo, tmp_path)
    save_agy(repo)
    atomic_agy_save(link, {
        **AGY_BASE,
        "queuedMessages": "send-immediately",
        **AGY_VALUES,
    })

    result = isolated_picks(repo, home, "forget", AGY)

    assert result.returncode == 0, result.stderr
    assert link.is_symlink() and link.resolve() == (repo / AGY).resolve()
    assert agy_settings(repo) == {**AGY_BASE, "queuedMessages": "send-immediately"}
    assert json.loads(agy_record_path(repo).read_text()) == {AGY: {"state": "default"}}
    assert isolated_git(repo, home, "status", "--porcelain").stdout == f" M {AGY}\n"


def test_agy_unanchored_home_regular_file_is_left_untouched(repo, tmp_path):
    home = tmp_path / "unanchored-home"
    (home / ".gemini/antigravity-cli").mkdir(parents=True)
    regular = home / ".gemini/antigravity-cli/settings.json"
    raw = '{"trustedWorkspaces": ["/unanchored"]}\n'
    regular.write_text(raw)
    repo_before = (repo / AGY).read_bytes()

    result = isolated_picks(repo, home, "sync")

    assert result.returncode == 0, result.stderr
    assert not regular.is_symlink()
    assert regular.read_text() == raw
    assert (repo / AGY).read_bytes() == repo_before
    assert not agy_record_path(repo).exists()


def first_run_agy_home(tmp_path, data):
    """A host agy ran on before this checkout linked its home: real dirs, no anchors."""
    home = tmp_path / "first-run-home"
    (home / ".gemini/antigravity-cli").mkdir(parents=True)
    (home / ".gemini/config").mkdir(parents=True)
    path = home / ".gemini/antigravity-cli/settings.json"
    path.write_text(json.dumps(data, indent=2) + "\n")
    stub_pgrep(home)
    return home, path


def stub_pgrep(home, running=""):
    """A pgrep on the isolated PATH: live-picks first-run never sees this host's agy."""
    bin_dir = home / ".test-bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    pgrep = bin_dir / "pgrep"
    pgrep.write_text(f"#!/bin/sh\nprintf '%s' '{running}'\n" + ("exit 0\n" if running else "exit 1\n"))
    pgrep.chmod(0o755)


def test_agy_first_run_file_is_merged_onto_the_tracked_config_and_relinked(repo, tmp_path):
    write_agy(repo, showFeedbackSurvey=False)
    git(repo, "commit", "-q", "-am", "track showFeedbackSurvey")
    write_agy(repo, showFeedbackSurvey=False, model="Gemini 4 Argon (Medium)",
              trustedWorkspaces=["/work/a"])
    save_agy(repo, {"model": "Gemini 4 Argon (Medium)", "trustedWorkspaces": ["/work/a"],
                    "effort": "high", "effortByBase": {"Gemini 4 Argon": "high"}})
    home, path = first_run_agy_home(tmp_path, {
        "model": "Gemini 4 Argon (Low)",
        "seasonalThemesOptIn": "halloween-2026",
        "showFeedbackSurvey": False,
        "trustedWorkspaces": ["/work/b", "/work/a"],
    })

    result = isolated_picks(repo, home, "first-run")

    assert result.returncode == 0, result.stderr
    assert path.is_symlink() and path.resolve() == (repo / AGY).resolve()
    want = {"model": "Gemini 4 Argon (Medium)", "effort": "high",
            "effortByBase": {"Gemini 4 Argon": "high"},
            "trustedWorkspaces": ["/work/a", "/work/b"], "seasonalThemesOptIn": "halloween-2026"}
    assert agy_settings(repo) == {**AGY_BASE, "showFeedbackSurvey": False, **want}
    assert json.loads(agy_record_path(repo).read_text()) == {AGY: {"state": "set", "values": want}}
    assert isolated_git(repo, home, "diff", "--quiet", "--", AGY, check=False).returncode == 0


def test_agy_first_run_file_with_a_key_the_config_lacks_is_refused_untouched(repo, tmp_path):
    write_agy(repo, showFeedbackSurvey=True)
    repo_before = (repo / AGY).read_bytes()
    home, path = first_run_agy_home(tmp_path, {
        "queuedMessages": "send-immediately",
        "showFeedbackSurvey": False,
        "trustedWorkspaces": ["/first-run"],
    })
    raw = path.read_text()

    result = isolated_picks(repo, home, "first-run")

    assert result.returncode != 0
    assert "queuedMessages, showFeedbackSurvey" in result.stderr
    assert "nothing written" in result.stderr
    assert "Traceback" not in result.stderr
    assert not path.is_symlink() and path.read_text() == raw
    assert (repo / AGY).read_bytes() == repo_before
    assert not agy_record_path(repo).exists()


def test_agy_first_run_refuses_an_anchored_home_and_a_corrupt_file(repo, tmp_path):
    home, link = anchor_agy_home(repo, tmp_path)
    repo_before = (repo / AGY).read_bytes()
    atomic_agy_save(link, {**AGY_BASE, "model": "Gemini 4 Argon (High)"})

    anchored = isolated_picks(repo, home, "first-run")

    assert anchored.returncode != 0
    assert "anchored" in anchored.stderr and "live-picks sync" in anchored.stderr
    assert not link.is_symlink()
    assert (repo / AGY).read_bytes() == repo_before

    home, path = first_run_agy_home(tmp_path / "corrupt", {})
    path.write_text("{corrupt\n")

    corrupt = isolated_picks(repo, home, "first-run")

    assert corrupt.returncode != 0
    assert f"{path} does not parse" in corrupt.stderr
    assert not path.is_symlink() and path.read_text() == "{corrupt\n"
    assert (repo / AGY).read_bytes() == repo_before


def test_agy_first_run_refuses_while_agy_runs(repo, tmp_path):
    home, path = first_run_agy_home(tmp_path, {"trustedWorkspaces": ["/first-run"]})
    stub_pgrep(home, running="4242")
    raw = path.read_text()
    repo_before = (repo / AGY).read_bytes()

    result = isolated_picks(repo, home, "first-run")

    assert result.returncode != 0
    assert "agy is running (pid 4242)" in result.stderr and "quit every agy session" in result.stderr
    assert not path.is_symlink() and path.read_text() == raw
    assert (repo / AGY).read_bytes() == repo_before
    assert not agy_record_path(repo).exists()


def test_agy_first_run_without_a_regular_file_writes_nothing(repo, tmp_path):
    home, path = first_run_agy_home(tmp_path, {})
    path.unlink()
    repo_before = (repo / AGY).read_bytes()

    result = isolated_picks(repo, home, "first-run")

    assert result.returncode == 0, result.stderr
    assert not path.exists() and not path.is_symlink()
    assert (repo / AGY).read_bytes() == repo_before
    assert not agy_record_path(repo).exists()


def test_agy_corrupt_detached_file_or_record_refuses_without_clobbering(repo, tmp_path):
    home, link = anchor_agy_home(repo, tmp_path)
    write_claude(repo, model="sonnet")
    repo_before = (repo / AGY).read_bytes()
    link.unlink()
    link.write_text("{corrupt\n")

    bad_file = isolated_picks(repo, home, "sync")

    assert bad_file.returncode != 0
    assert "does not parse" in bad_file.stderr
    assert not link.is_symlink() and link.read_text() == "{corrupt\n"
    assert (repo / AGY).read_bytes() == repo_before
    assert record(repo)[CLAUDE] == {"state": "set", "values": {"model": "sonnet"}}

    atomic_agy_save(link, {**AGY_BASE, **AGY_VALUES})
    agy_record_path(repo).write_text("{corrupt-record\n")

    bad_record = isolated_picks(repo, home, "sync")

    assert bad_record.returncode != 0
    assert "local/live-picks-agy.json" in bad_record.stderr
    assert agy_record_path(repo).read_text() == "{corrupt-record\n"
    assert not link.is_symlink()
    assert (repo / AGY).read_bytes() == repo_before


def test_agy_foreign_symlink_is_ignored_and_directory_at_link_is_refused(repo, tmp_path):
    home, link = anchor_agy_home(repo, tmp_path)
    foreign = tmp_path / "foreign-settings.json"
    foreign.write_text('{"model": "Foreign"}\n')
    link.unlink()
    link.symlink_to(foreign)

    foreign_res = isolated_picks(repo, home, "sync")

    assert foreign_res.returncode == 0, foreign_res.stderr
    assert os.readlink(link) == str(foreign)
    assert not agy_record_path(repo).exists()

    link.unlink()
    link.mkdir()

    dir_res = isolated_picks(repo, home, "sync")

    assert dir_res.returncode != 0
    assert "not a regular file" in dir_res.stderr
    assert "Traceback" not in dir_res.stderr
    assert link.is_dir() and not link.is_symlink()


@pytest.mark.parametrize("damage", ["conflict", "syntax"])
def test_unimportable_harness_state_hook_exits_zero_with_retry_while_cli_fails(
        repo, tmp_path, damage):
    home = isolated_home(repo, tmp_path)
    module = repo / ".githooks/harness_state.py"
    module.write_text("<<<<<<< ours\nx = 1\n=======\nx = 2\n>>>>>>> theirs\n"
                      if damage == "conflict" else "def (:\n")

    hook = isolated_picks(repo, home, "hook", "post-merge")
    cli = isolated_picks(repo, home, "capture")

    assert hook.returncode == 0, hook.stderr
    assert "live-picks: cannot load .githooks/harness_state.py: " in hook.stderr
    assert "resolve or restore it" in hook.stderr
    assert "the next turn end retries" in hook.stderr
    assert cli.returncode != 0
    assert cli.stderr.startswith("live-picks: cannot load .githooks/harness_state.py: ")
    for result in (hook, cli):
        assert "Traceback" not in result.stderr
