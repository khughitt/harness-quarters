"""The default pre-commit hook refuses a staged Codex config whose developer_instructions is not
lore's current long-wait rule, reading the staged tree, never the working file."""
import importlib.machinery
import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).with_name("pre-commit")
CHECKOUT = HOOK.parent.parent
CONFIG = "harnesses/codex/config.toml"
TOOL = "tools/codex-instructions"


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


hook = load("pre_commit", HOOK)
tool_tests = load("test_codex_instructions", CHECKOUT / "tools" / "test_codex_instructions.py")


def git(*args):
    return subprocess.run(["git", *args], check=True, text=True, capture_output=True).stdout


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A scratch repository with the staged tool, its harness_state import and a current
    config; the environment is rebuilt key by key with git config kept under tmp_path."""
    root, home = tmp_path / "repo", tmp_path / "home"
    home.mkdir()
    (tmp_path / "gitconfig").touch()
    env = {"PATH": os.environ["PATH"], "HOME": str(home), "XDG_CONFIG_HOME": str(tmp_path / "config"),
           "GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig"), "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
           "PYTHONDONTWRITEBYTECODE": "1"}
    for key in list(os.environ):
        monkeypatch.delenv(key)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    monkeypatch.chdir(root)
    assert Path(git("rev-parse", "--show-toplevel").strip()) == root.resolve()
    assert Path(git("rev-parse", "--absolute-git-dir").strip()).is_relative_to(root.resolve())
    for name in (TOOL, ".githooks/harness_state.py"):
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(CHECKOUT / name, root / name)
    (root / CONFIG).parent.mkdir(parents=True)
    (root / CONFIG).write_text(stale_config())
    git("add", ".")
    git("-c", "commit.gpgsign=false", "commit", "-q", "--no-verify", "-m", "base")
    return root


@pytest.fixture
def lore(tmp_path):
    return tool_tests.make_lore(tmp_path / "lore", tool_tests.RULE_TEXT)


def stale_config():
    return 'model = "m"\ndeveloper_instructions = ""\n'


def current_config():
    return 'model = "m"\n' + tool_tests.tool.value_line(tool_tests.RENDERED)


def staged_codex_check(lore):
    return hook.with_staged_tree(lambda tree: hook.codex_check(tree, lore=str(lore)))


def test_current_staged_config_passes(repo, lore):
    (repo / CONFIG).write_text(current_config())
    git("add", CONFIG)
    assert staged_codex_check(lore) == 0


def test_stale_staged_value_under_fresh_working_file_is_refused(repo, lore, capsys):
    (repo / CONFIG).write_text(current_config())
    assert staged_codex_check(lore) == 1
    err = capsys.readouterr().err
    assert CONFIG in err and "ask the user to approve" in err
    assert "staged-tree-" not in err


def test_fresh_staged_value_passes_over_stale_working_file(repo, lore):
    (repo / CONFIG).write_text(current_config())
    git("add", CONFIG)
    (repo / CONFIG).write_text(stale_config())
    assert staged_codex_check(lore) == 0


def test_unstaged_tool_is_refused(repo, lore, capsys):
    (repo / CONFIG).write_text(current_config())
    git("add", CONFIG)
    git("rm", "-q", "--cached", TOOL)
    assert staged_codex_check(lore) == 1
    assert f"{TOOL} is not staged" in capsys.readouterr().err


def test_missing_lore_is_refused(repo, tmp_path, capsys):
    (repo / CONFIG).write_text(current_config())
    git("add", CONFIG)
    assert staged_codex_check(tmp_path / "absent") == 1
    err = capsys.readouterr().err
    assert "cannot read lore's manifest" in err
    assert "ask the user to approve" not in err


def test_ci_mode_does_not_run_the_codex_check(monkeypatch):
    monkeypatch.setattr(hook, "local_layer", lambda: 0)
    monkeypatch.setattr(hook, "docs_check", lambda: 0)
    monkeypatch.setattr(hook, "with_staged_tree", lambda check: check(Path("/nonexistent")))
    monkeypatch.setattr(hook, "facts_check", lambda tree: 0)
    monkeypatch.setattr(hook, "manifest_check", lambda tree, git_dir=None: 0)
    monkeypatch.setattr(hook, "real_git_dir", lambda: "/nonexistent")
    monkeypatch.setattr(hook, "codex_check", lambda tree, lore=None: pytest.fail("CI ran the codex check"))
    assert hook.main(["--ci"]) == 0
