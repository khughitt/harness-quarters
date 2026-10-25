"""The pre-commit hook runs the shared hygiene checks, validates residue docs and refuses
staged local state."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).with_name("pre-commit")
OPS_CHECK = Path(__file__).resolve().parent.parent / "tools" / "ops-check"


def sh(cwd, env, *args):
    return subprocess.run(args, cwd=cwd, env=env, check=True, text=True, capture_output=True).stdout


DOCS_OK = "#!/usr/bin/env python3\nimport sys\nassert sys.argv[1:] == ['check']\n"


def docs_stub(repo, body=DOCS_OK):
    tool = repo / "tools" / "ops-docs"
    tool.parent.mkdir(exist_ok=True)
    tool.write_text(body)
    tool.chmod(0o755)


@pytest.fixture
def world(tmp_path):
    """An isolated repository with the vendored hygiene checker, a passing docs tool and no
    local files. The environment is built key by key: HOME and an empty XDG_CONFIG_HOME
    under tmp_path, so the checker reads no real registry, banned list, home or WORK_ROOT,
    and git reads no real config; no inherited GIT_* variable comes along."""
    home, config, gitconfig = tmp_path / "home", tmp_path / "config", tmp_path / "gitconfig"
    home.mkdir()
    config.mkdir()
    gitconfig.write_text("")
    env = {"PATH": os.environ["PATH"], "HOME": str(home), "XDG_CONFIG_HOME": str(config),
           "GIT_CONFIG_GLOBAL": str(gitconfig), "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    repo = tmp_path / "ai"
    repo.mkdir()
    sh(repo, env, "git", "init", "-q")
    top = Path(sh(repo, env, "git", "rev-parse", "--show-toplevel").strip())
    git_dir = Path(sh(repo, env, "git", "rev-parse", "--absolute-git-dir").strip())
    assert top == repo.resolve() and git_dir.is_relative_to(repo.resolve()), (top, git_dir)
    (repo / "AGENTS.md").write_text("# rules\n")
    docs_stub(repo)
    facts = repo / "tools" / "harness-facts"                   # the staged tree's fact reader passes
    facts.write_text("#!/usr/bin/env python3\nimport sys\nassert sys.argv[1:] == ['check']\n")
    shutil.copyfile(OPS_CHECK, repo / "tools" / "ops-check")
    (repo / "tools" / "ops-check").chmod(0o755)
    sh(repo, env, "git", "add", "AGENTS.md", "tools/harness-facts", "tools/ops-check")
    sh(repo, env, "git", "commit", "-q", "-m", "init")
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
    sh(repo, env, "git", "add", "README.md")
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
    sh(repo, env, "git", "add", "-f", "local/settings.work.json")
    result = run_hook(repo, env)
    assert result.returncode == 1
    assert "local/settings.work.json" in result.stderr


def test_refuses_a_rename_into_local(world):
    repo, env, _ = world
    (repo / "settings.work.json").write_text("{}\n")
    sh(repo, env, "git", "add", "settings.work.json")
    sh(repo, env, "git", "commit", "-q", "-m", "tracked")
    (repo / "local").mkdir()
    sh(repo, env, "git", "mv", "settings.work.json", "local/settings.work.json")
    result = run_hook(repo, env)
    assert result.returncode == 1
    assert "local/settings.work.json" in result.stderr


def test_passes_when_nothing_under_local_is_staged(world):
    repo, env, _ = world
    (repo / "notes.md").write_text("x\n")
    sh(repo, env, "git", "add", "notes.md")
    assert run_hook(repo, env).returncode == 0


def test_a_layout_finding_refuses_before_the_docs_check(world):
    repo, env, tmp_path = world
    marker = tmp_path / "docs-ran"
    docs_stub(repo, f"#!/usr/bin/env python3\nimport pathlib\npathlib.Path({str(marker)!r}).touch()\n")
    (repo / "notes.md").write_text(f"see {env['HOME']}/notes\n")   # the fake HOME is a layout value
    sh(repo, env, "git", "add", "notes.md")
    result = run_hook(repo, env)
    assert result.returncode == 1
    assert "machine layout" in result.stderr
    assert not marker.exists()


def test_a_missing_ops_check_refuses(world):
    repo, env, _ = world
    (repo / "tools" / "ops-check").unlink()
    result = run_hook(repo, env)
    assert result.returncode == 1
    assert "tools/ops-check" in result.stderr
    assert "vendored adopt ops-check" in result.stderr


def test_an_ops_check_that_cannot_run_refuses(world):
    repo, env, _ = world
    (repo / ".ops-check.toml").write_text('layout_allowed = "x"\n')   # malformed: the checker exits 2
    sh(repo, env, "git", "add", ".ops-check.toml")
    result = run_hook(repo, env)
    assert result.returncode == 1
    assert "ops-check:" in result.stderr
    assert "could not run (exit 2)" in result.stderr


def test_a_clean_tree_passes_the_hygiene_check(world):
    repo, env, _ = world
    (repo / "notes.md").write_text("nothing host-specific here\n")
    sh(repo, env, "git", "add", "notes.md")
    assert run_hook(repo, env).returncode == 0


def test_a_local_refusal_is_not_masked_by_a_layout_finding(world):
    repo, env, _ = world
    (repo / ".gitignore").write_text("local/\n")
    (repo / "local").mkdir()
    (repo / "local" / "settings.work.json").write_text(f'{{"home": "{env['HOME']}"}}\n')
    sh(repo, env, "git", "add", "-f", "local/settings.work.json")
    result = run_hook(repo, env)
    assert result.returncode == 1
    assert "staged paths under local/" in result.stderr
    assert "machine layout" not in result.stderr
