"""Standalone decoder provenance and shared harness home discovery."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import harness_stores  # noqa: E402
from harness_evidence import homes  # noqa: E402


def clean_env(tmp_path):
    user_home = tmp_path / "user-home"
    user_home.mkdir(exist_ok=True)
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(user_home),
        "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    }


def run(argv, root, env):
    return subprocess.run(argv, cwd=root, env=env, capture_output=True, text=True)


def git(root, env, *args):
    proc = run(["git", *args], root, env)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def extracted_copy(tmp_path, revision=None):
    root = tmp_path / "copy"
    tools = root / "tools"
    tools.mkdir(parents=True)
    shutil.copytree(TOOLS / "harness_evidence", tools / "harness_evidence",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(TOOLS / "harness-evidence", tools / "harness-evidence")
    if revision is not None:
        (tools / "harness_evidence" / "REVISION").write_text(revision + "\n")
    return root


def version(root, env):
    return run([str(root / "tools" / "harness-evidence"), "version", "--json"], root, env)


def version_json(root, env):
    proc = version(root, env)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def fixture_repo(tmp_path):
    root = extracted_copy(tmp_path)
    (root / "tools" / ".gitignore").write_text("__pycache__/\n")
    env = clean_env(tmp_path)
    git(root, env, "init", "-q")
    # Prove writes cannot reach a repository selected by inherited hook variables.
    assert Path(git(root, env, "rev-parse", "--show-toplevel")) == root.resolve()
    assert Path(git(root, env, "rev-parse", "--absolute-git-dir")).is_relative_to(root.resolve())
    git(root, env, "add", "tools")
    git(root, env, "commit", "-qm", "fixture")
    return root, env


def test_package_imports_no_hq_internals(tmp_path):
    probe = (
        f"import sys; sys.path.insert(0, {str(TOOLS)!r}); "
        "import harness_evidence, harness_evidence.__main__, json; "
        "print(json.dumps(sorted(set(sys.modules) & "
        "{'hq_cli', 'session_archive', 'harness_stores', 'obs'})))"
    )
    proc = run([sys.executable, "-I", "-c", probe], tmp_path, clean_env(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == []


def test_homes_are_the_store_adapters_homes(tmp_path):
    for adapter in harness_stores.ADAPTERS:
        assert adapter.homes(tmp_path) == homes.homes(tmp_path, adapter.alias)
    assert harness_stores.Home is homes.Home
    assert harness_stores.homes(tmp_path) == homes.homes(tmp_path)


@pytest.mark.parametrize("harness, expected", [
    ("claude", [("claude", "personal", ".claude"), ("claude-work", "work", ".claude-work")]),
    ("codex", [("codex", "personal", ".codex"), ("codex-work", "work", ".codex-work")]),
    ("agy", [("agy", "personal", ".gemini/antigravity-cli")]),
])
def test_home_paths_and_stores(tmp_path, harness, expected):
    found = homes.homes(tmp_path, harness)
    assert [(h.name, h.kind, str(h.path.relative_to(tmp_path))) for h in found] == expected
    for home in found:
        assert home.harness == harness
        expected_stores = {
            "claude": (("live", home.path / "projects"),),
            "codex": (("live", home.path / "sessions"), ("archived", home.path / "archived_sessions")),
            "agy": (("live", home.path / "brain"),),
        }
        assert homes.stores(home) == expected_stores[harness]


def test_unknown_harness_fails_explicitly(tmp_path):
    with pytest.raises(KeyError, match="nope"):
        homes.homes(tmp_path, "nope")
    with pytest.raises(KeyError, match="nope"):
        homes.stores(homes.Home("nope", "nope", "personal", tmp_path))


def test_checkout_revision_is_head_and_marks_dirty(tmp_path):
    root, env = fixture_repo(tmp_path)
    head = git(root, env, "rev-parse", "HEAD")
    output = version_json(root, env)
    assert output == {"schema": "harness-evidence/1", "decoder": {"version": "7", "revision": head}}
    (root / "unrelated").write_text("outside package\n")
    assert version_json(root, env)["decoder"]["revision"] == head
    extra = root / "tools" / "harness_evidence" / "extra.py"
    extra.write_text("")
    assert version_json(root, env)["decoder"]["revision"] == head + "+dirty"
    extra.unlink()
    (root / "tools" / "harness_evidence" / "homes.py").unlink()
    assert version_json(root, env)["decoder"]["revision"] == head + "+dirty"


@pytest.mark.parametrize("context", ["git-dir", "work-tree", "index", "combined"])
def test_checkout_revision_ignores_inherited_git_context(tmp_path, context):
    root, env = fixture_repo(tmp_path / "containing")
    foreign, foreign_env = fixture_repo(tmp_path / "foreign")
    (foreign / "tools" / "harness_evidence" / "foreign-only").write_text("other checkout\n")
    git(foreign, foreign_env, "add", "tools")
    git(foreign, foreign_env, "commit", "-qm", "foreign checkout")
    head = git(root, env, "rev-parse", "HEAD")
    assert git(foreign, foreign_env, "rev-parse", "HEAD") != head

    hostile_env = clean_env(tmp_path)
    if context in ("git-dir", "combined"):
        hostile_env["GIT_DIR"] = str(foreign / ".git")
    if context in ("work-tree", "combined"):
        hostile_env["GIT_WORK_TREE"] = str(foreign)
    if context in ("index", "combined"):
        hostile_env["GIT_INDEX_FILE"] = str(foreign / ".git" / "index")
    assert version_json(root, hostile_env)["decoder"]["revision"] == head
    (root / "tools" / "harness_evidence" / "extra.py").write_text("")
    assert version_json(root, hostile_env)["decoder"]["revision"] == head + "+dirty"


def test_pinned_copy_reads_revision_file(tmp_path):
    root = extracted_copy(tmp_path, revision="a" * 40)
    assert not any((p / ".git").exists() for p in (root, *root.parents))
    assert version_json(root, clean_env(tmp_path))["decoder"]["revision"] == "a" * 40


def test_pinned_revision_takes_priority_over_checkout(tmp_path):
    root, env = fixture_repo(tmp_path)
    (root / "tools" / "harness_evidence" / "REVISION").write_text("b" * 40 + "\n")
    assert version_json(root, env)["decoder"]["revision"] == "b" * 40


@pytest.mark.parametrize("revision", [None, ""])
def test_no_revision_source_exits_2(tmp_path, revision):
    root = extracted_copy(tmp_path, revision=revision)
    proc = version(root, clean_env(tmp_path))
    assert proc.returncode == 2
    assert "decoder revision unknown" in proc.stderr
    assert proc.stdout == ""
