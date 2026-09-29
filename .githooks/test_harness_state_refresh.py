"""The harness-state refresh clears git's size-only "modified" mark and stages nothing real."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

HOOKS = Path(__file__).parent
SETTINGS = "claude/settings.json"


def git(repo, *args, check=True):
    return subprocess.run(["git", "-C", str(repo), *args], check=check, text=True,
                          capture_output=True)


def write_settings(repo, **extra):
    data = {"theme": "dark-ansi", **extra}
    (repo / SETTINGS).write_text(json.dumps(data, indent=2) + "\n")


@pytest.fixture
def repo(tmp_path):
    """A checkout shaped like this one: the filter, the refresh, and a filtered settings file."""
    repo = tmp_path / "ai"
    (repo / ".githooks").mkdir(parents=True)
    (repo / "claude").mkdir()
    for name in ("harness-state-clean", "harness-state-refresh"):
        shutil.copy2(HOOKS / name, repo / ".githooks" / name)
    (repo / ".gitattributes").write_text("claude/settings*.json filter=harness-state\n")
    git(tmp_path, "init", "-q", str(repo))
    git(repo, "config", "filter.harness-state.clean", ".githooks/harness-state-clean %f")
    git(repo, "config", "user.email", "t@example.invalid")
    git(repo, "config", "user.name", "t")
    write_settings(repo, model="opus")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def refresh(repo, cwd):
    """Run the refresh as a harness hook would: from another directory, payload on stdin."""
    return subprocess.run([str(repo / ".githooks" / "harness-state-refresh")], cwd=cwd,
                          input='{"hook_event_name":"Stop"}', text=True, capture_output=True)


def marked(repo):
    return git(repo, "diff-files", "--quiet", "--", SETTINGS, check=False).returncode == 1


def test_a_model_switch_mark_is_cleared_from_any_cwd(repo, tmp_path):
    write_settings(repo, model="claude-sonnet-5")
    assert marked(repo)

    result = refresh(repo, cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert not marked(repo)
    assert git(repo, "diff", "--cached", "--quiet", check=False).returncode == 0


def test_a_real_change_stays_unstaged(repo, tmp_path):
    write_settings(repo, model="claude-sonnet-5", enabledPlugins={"x@y": True})

    result = refresh(repo, cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    assert marked(repo)
    assert git(repo, "diff", "--cached", "--quiet", check=False).returncode == 0


def test_a_held_index_lock_skips_without_failing(repo, tmp_path):
    write_settings(repo, model="claude-sonnet-5")
    lock = Path(git(repo, "rev-parse", "--git-path", "index.lock").stdout.strip())
    lock = lock if lock.is_absolute() else repo / lock
    lock.write_text("")

    result = refresh(repo, cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert lock.read_text() == ""
    lock.unlink()
    assert marked(repo)
