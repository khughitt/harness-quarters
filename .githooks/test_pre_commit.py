"""The pre-commit hook validates residue docs and refuses staged local state."""
import os
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).with_name("pre-commit")


def sh(cwd, *args, **kw):
    return subprocess.run(args, cwd=cwd, check=True, text=True, capture_output=True, **kw).stdout


DOCS_OK = "#!/usr/bin/env python3\nimport sys\nassert sys.argv[1:] == ['check']\n"


def docs_stub(repo, body=DOCS_OK):
    tool = repo / "tools" / "ops-docs"
    tool.parent.mkdir(exist_ok=True)
    tool.write_text(body)
    tool.chmod(0o755)


@pytest.fixture
def world(tmp_path):
    """An isolated repository with a passing docs tool and no local files."""
    repo = tmp_path / "ai"
    repo.mkdir()
    sh(repo, "git", "init", "-q")
    sh(repo, "git", "config", "user.email", "t@example.com")
    sh(repo, "git", "config", "user.name", "t")
    (repo / "AGENTS.md").write_text("# rules\n")
    docs_stub(repo)
    sh(repo, "git", "add", "AGENTS.md")
    sh(repo, "git", "commit", "-q", "-m", "init")
    env = {**os.environ, "XDG_CONFIG_HOME": str(tmp_path / "config")}
    return repo, env, tmp_path


def run_hook(repo, env):
    return subprocess.run([str(HOOK)], cwd=repo, env=env, text=True, capture_output=True)


def test_runs_the_docs_check_and_fails_with_its_output(world):
    repo, env, _ = world
    docs_stub(repo, "#!/usr/bin/env python3\nimport sys\nsys.stderr.write('ops-docs: README.md: identity region is missing\\n')\nsys.exit(1)\n")
    result = run_hook(repo, env)
    assert result.returncode == 1
    assert "identity region is missing" in result.stderr
    assert "just docs" in result.stderr


def test_runs_the_docs_check_when_agents_md_is_not_staged(world):
    repo, env, _ = world
    docs_stub(repo, "#!/usr/bin/env python3\nimport sys\nsys.exit(1)\n")
    (repo / "README.md").write_text("x\n")
    sh(repo, "git", "add", "README.md")
    assert run_hook(repo, env).returncode == 1


def test_fails_loudly_when_ops_docs_is_missing(world):
    repo, env, _ = world
    (repo / "tools" / "ops-docs").unlink()
    result = run_hook(repo, env)
    assert result.returncode == 1
    assert "tools/ops-docs" in result.stderr


def test_refuses_a_force_added_local_file(world):
    repo, env, _ = world
    (repo / ".gitignore").write_text("local/\n")
    (repo / "local").mkdir()
    (repo / "local" / "settings.work.json").write_text("{}\n")
    sh(repo, "git", "add", "-f", "local/settings.work.json")
    result = run_hook(repo, env)
    assert result.returncode == 1
    assert "local/settings.work.json" in result.stderr


def test_refuses_a_rename_into_local(world):
    repo, env, _ = world
    (repo / "settings.work.json").write_text("{}\n")
    sh(repo, "git", "add", "settings.work.json")
    sh(repo, "git", "commit", "-q", "-m", "tracked")
    (repo / "local").mkdir()
    sh(repo, "git", "mv", "settings.work.json", "local/settings.work.json")
    result = run_hook(repo, env)
    assert result.returncode == 1
    assert "local/settings.work.json" in result.stderr


def test_passes_when_nothing_under_local_is_staged(world):
    repo, env, _ = world
    (repo / "notes.md").write_text("x\n")
    sh(repo, "git", "add", "notes.md")
    assert run_hook(repo, env).returncode == 0
