"""pre-commit validates a staged fact file as staged, not as it sits in the working tree."""
import importlib.machinery
import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).with_name("pre-commit")
CHECKOUT = HOOK.parent.parent


def load_hook():
    loader = importlib.machinery.SourceFileLoader("pre_commit", str(HOOK))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A scratch repository holding the tool, the probe it names, and the shipped fact file."""
    root = tmp_path / "repo"
    for name in ("tools/harness-facts", "agents/bin/wake-judge", "facts/capabilities.toml"):
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(CHECKOUT / name, root / name)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    monkeypatch.chdir(root)
    monkeypatch.delenv("FACTS_MIRROR_OPS", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))   # no registry: the mirror cannot run
    return root


def stage(root, text=None):
    path = root / "facts" / "capabilities.toml"
    if text is not None:
        path.write_text(text)
    subprocess.run(["git", "add", "facts/capabilities.toml"], cwd=root, check=True)
    return path


def test_an_unstaged_fact_file_is_not_checked(repo):
    (repo / "facts" / "capabilities.toml").write_text("not toml at all [")
    assert load_hook().facts_check() == 0


def test_a_valid_staged_file_passes(repo, capsys):
    stage(repo)
    assert load_hook().facts_check() == 0


def test_an_invalid_staged_file_is_refused(repo, capsys):
    stage(repo, (repo / "facts" / "capabilities.toml").read_text().replace("schema = 1", "schema = 2"))
    assert load_hook().facts_check() == 1
    assert "schema must be 1" in capsys.readouterr().err


def test_the_staged_blob_is_what_is_checked(repo, capsys):
    good = (repo / "facts" / "capabilities.toml").read_text()
    stage(repo, good.replace("schema = 1", "schema = 2"))
    (repo / "facts" / "capabilities.toml").write_text(good)        # the working tree is fixed; the index is not
    assert load_hook().facts_check() == 1


STUB_JUSTFILE = '''
test-one +args:
    python3 mirror.py {{args}}
'''
STUB_MIRROR = '''
"""A scratch copy of the guard's side: it holds that claude-code wakes its controller."""
import importlib.machinery, importlib.util, os, pathlib, sys
pathlib.Path("ran").write_text(" ".join(sys.argv[1:]))
pathlib.Path("gitenv").write_text(" ".join(sorted(k for k in os.environ if k.startswith("GIT_"))))
tool = os.environ["HARNESS_FACTS_TOOL"]
loader = importlib.machinery.SourceFileLoader("harness_facts", tool)
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)
entry = module.lookup("controller-wake", "claude-code", os.environ["HARNESS_FACTS_FILE"])
sys.exit(0 if entry.get("value") is True else 1)
'''


@pytest.fixture
def ops(tmp_path, monkeypatch):
    root = tmp_path / "ops"
    root.mkdir()
    (root / "justfile").write_text(STUB_JUSTFILE)
    (root / "mirror.py").write_text(STUB_MIRROR)
    (root / "tests").mkdir()
    (root / "tests" / "test_claim_guard.py").write_text("")   # what makes it ops
    monkeypatch.setenv("FACTS_MIRROR_OPS", str(root))
    return root


def test_a_staged_file_the_guard_agrees_with_passes(repo, ops):
    stage(repo)
    assert load_hook().facts_check() == 0
    assert (ops / "ran").read_text() == "tests.test_claim_guard.FactsMirrorTests"


def test_a_staged_file_the_guard_disagrees_with_is_refused(repo, ops, capsys):
    stage(repo, (repo / "facts" / "capabilities.toml").read_text().replace("value = true", "value = false", 1))
    assert load_hook().facts_check() == 1
    assert "claim-guard" in capsys.readouterr().err


def test_an_unstaged_file_never_runs_the_mirror(repo, ops):
    assert load_hook().facts_check() == 0
    assert not (ops / "ran").exists()


def test_an_unregistered_ops_is_a_notice(repo, capsys):
    stage(repo)                                   # the fixture's registry is empty and FACTS_MIRROR_OPS is unset
    assert load_hook().facts_check() == 0
    assert "the claim-guard mirror was not checked" in capsys.readouterr().err


def test_a_missing_registered_ops_is_a_notice(repo, tmp_path, capsys):
    (tmp_path / "config" / "tasks").mkdir(parents=True)
    (tmp_path / "config" / "tasks" / "projects.toml").write_text(f'[projects]\nops = "{tmp_path / "gone"}"\n')
    stage(repo)
    assert load_hook().facts_check() == 0
    assert "the claim-guard mirror was not checked" in capsys.readouterr().err


def test_a_named_ops_that_is_missing_is_refused(repo, tmp_path, monkeypatch, capsys):
    """A person who names a worktree for a value change asked for the check: a typo refuses."""
    monkeypatch.setenv("FACTS_MIRROR_OPS", str(tmp_path / "gone"))
    stage(repo)
    assert load_hook().facts_check() == 1
    assert "FACTS_MIRROR_OPS" in capsys.readouterr().err


def test_a_named_directory_that_is_not_ops_is_refused(repo, ops, capsys):
    (ops / "tests" / "test_claim_guard.py").unlink()
    stage(repo)
    assert load_hook().facts_check() == 1
    assert "FACTS_MIRROR_OPS" in capsys.readouterr().err
    assert not (ops / "ran").exists()


def test_a_mirror_that_hangs_is_refused(repo, ops, capsys):
    (ops / "justfile").write_text("test-one +args:\n    sleep 30\n")
    hook = load_hook()
    hook.MIRROR_TIMEOUT = 1
    stage(repo)
    assert hook.facts_check() == 1
    assert "timed out" in capsys.readouterr().err


def test_a_missing_just_is_a_notice(repo, ops, monkeypatch, capsys):
    hook = load_hook()
    monkeypatch.setattr(hook.shutil, "which", lambda name: None)
    stage(repo)
    assert hook.facts_check() == 0
    assert "the claim-guard mirror was not checked" in capsys.readouterr().err
    assert not (ops / "ran").exists()


def test_gits_hook_environment_does_not_reach_ops(repo, ops, monkeypatch):
    """git exports the commit's GIT_DIR and index file to a hook; ops's recipes run git, and
    must run it against ops, never against this repository's in-flight commit."""
    monkeypatch.setenv("GIT_REFLOG_ACTION", "a-variable-git-would-export")
    stage(repo)
    assert load_hook().facts_check() == 0
    assert (ops / "gitenv").read_text() == ""
