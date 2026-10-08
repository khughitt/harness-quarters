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
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
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


def test_a_valid_value_change_needs_no_consumer_mirror(repo, monkeypatch):
    good = (repo / 'facts/capabilities.toml').read_text()
    stage(repo, good.replace('value = true', 'value = false', 1))
    hook = load_hook()
    def forbidden(candidate):
        raise AssertionError('consumer mirror still ran')
    monkeypatch.setattr(hook, 'mirror', forbidden, raising=False)
    assert hook.facts_check() == 0


def test_removed_mirror_command_is_refused(repo, capsys):
    assert load_hook().main(['facts-mirror']) == 1
    assert 'accepts no arguments' in capsys.readouterr().err
