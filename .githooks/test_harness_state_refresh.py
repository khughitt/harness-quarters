"""The harness-state refresh clears git's size-only "modified" mark and stages nothing real."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

HOOKS = Path(__file__).parent
SETTINGS = "claude/settings.json"
PI_SETTINGS = "pi/settings.json"
AGY_SETTINGS = "agy/settings.json"


def git(repo, *args, check=True):
    return subprocess.run(["git", "-C", str(repo), *args], check=check, text=True,
                          capture_output=True)


def write_settings(repo, **extra):
    data = {"theme": "dark-ansi", **extra}
    (repo / SETTINGS).write_text(json.dumps(data, indent=2) + "\n")


@pytest.fixture
def repo(tmp_path):
    """A checkout shaped like this one: the filter, the refresh, codex-trust, and filtered configs."""
    repo = tmp_path / "ai"
    (repo / ".githooks").mkdir(parents=True)
    (repo / "claude").mkdir()
    (repo / "codex").mkdir()
    (repo / "pi").mkdir()
    (repo / "agy").mkdir()
    (repo / "local" / "codex").mkdir(parents=True)
    for name in ("harness-state-clean", "harness-state-refresh", "codex-trust",
                 "harness_state.py", "live-picks"):
        shutil.copy2(HOOKS / name, repo / ".githooks" / name)
    (repo / ".gitattributes").write_text("claude/settings*.json filter=harness-state\n"
                                         "codex/config*.toml filter=harness-state\n"
                                         "pi/settings*.json filter=harness-state\n"
                                         "agy/settings*.json filter=harness-state\n")
    (repo / ".gitignore").write_text("local/\n__pycache__/\n")
    (repo / "codex" / "config.toml").write_text("[features]\nhooks = true\n")
    git(tmp_path, "init", "-q", str(repo))
    git(repo, "config", "filter.harness-state.clean", ".githooks/harness-state-clean %f")
    git(repo, "config", "user.email", "t@example.invalid")
    git(repo, "config", "user.name", "t")
    write_settings(repo, model="opus")
    (repo / PI_SETTINGS).write_text(json.dumps({"lastChangelogVersion": "1.1.0", "theme": "system"}, indent=2))
    (repo / AGY_SETTINGS).write_text(json.dumps(
        {"allowNonWorkspaceAccess": True, "permissions": {"allow": ["command(tasks)"]}}, indent=2) + "\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def refresh(repo, cwd):
    """Run the refresh as a harness hook would: from another directory, payload on stdin."""
    return subprocess.run([str(repo / ".githooks" / "harness-state-refresh")], cwd=cwd,
                          input='{"hook_event_name":"Stop"}', text=True, capture_output=True)


def marked(repo, path=SETTINGS):
    return git(repo, "diff-files", "--quiet", "--", path, check=False).returncode == 1


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


def test_a_sync_that_dies_without_a_message_still_fails_with_one(repo, tmp_path):
    trust = repo / ".githooks" / "codex-trust"
    trust.write_text("#!/bin/sh\nexit 3\n")

    result = refresh(repo, cwd=tmp_path)

    assert result.returncode != 0
    assert "codex-trust sync exited 3" in result.stderr


def test_a_pi_model_switch_mark_is_cleared(repo, tmp_path):
    (repo / PI_SETTINGS).write_text(json.dumps(
        {"lastChangelogVersion": "1.1.0", "theme": "system",
         "defaultProvider": "anthropic", "defaultModel": "claude-opus-5-5"},
        indent=2))
    assert marked(repo, PI_SETTINGS)

    result = refresh(repo, cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    assert not marked(repo, PI_SETTINGS)
    assert git(repo, "diff", "--cached", "--quiet", check=False).returncode == 0


def test_an_agy_model_or_trust_mark_is_cleared(repo, tmp_path):
    (repo / AGY_SETTINGS).write_text(json.dumps(
        {"allowNonWorkspaceAccess": True, "model": "Gemini 4 Argon (Medium)",
         "permissions": {"allow": ["command(tasks)"]}, "trustedWorkspaces": ["/work/a"]},
        indent=2) + "\n")
    assert marked(repo, AGY_SETTINGS)

    result = refresh(repo, cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    assert not marked(repo, AGY_SETTINGS)
    assert git(repo, "diff", "--cached", "--quiet", check=False).returncode == 0


def test_an_agy_replaced_regular_file_is_adopted_relinked_and_unmarked(repo, tmp_path):
    import os
    home = tmp_path / "home"
    (home / ".gemini/antigravity-cli").mkdir(parents=True)
    (home / ".gemini/config").mkdir(parents=True)
    env = {
        "PATH": os.environ["PATH"],
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
    (repo / "agy/hooks.json").write_text("{}\n")
    subprocess.run(["git", "-C", str(repo), "add", "agy/hooks.json"], env=env, check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "hooks"], env=env, check=True)
    (home / ".gemini/config/hooks.json").symlink_to(repo / "agy/hooks.json")
    link = home / ".gemini/antigravity-cli/settings.json"
    link.write_text(json.dumps({
        "allowNonWorkspaceAccess": True,
        "model": "Gemini 4 Argon (High)",
        "permissions": {"allow": ["command(tasks)"]},
        "trustedWorkspaces": ["/work/a", "/work/b"],
    }, indent=2) + "\n")
    link.chmod(0o600)

    result = subprocess.run([str(repo / ".githooks/harness-state-refresh")], cwd=tmp_path,
                            env=env, input='{"hook_event_name":"Stop"}', text=True,
                            capture_output=True)

    assert result.returncode == 0, result.stderr
    assert link.is_symlink() and link.resolve() == (repo / AGY_SETTINGS).resolve()
    assert json.loads((repo / AGY_SETTINGS).read_text())["model"] == "Gemini 4 Argon (High)"
    assert not marked(repo, AGY_SETTINGS)
    assert subprocess.run(["git", "-C", str(repo), "status", "--porcelain"], env=env,
                          text=True, capture_output=True).stdout == ""
