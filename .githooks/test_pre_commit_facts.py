"""pre-commit validates a staged fact file as staged, not as it sits in the working tree."""
import importlib.machinery
import importlib.util
import shutil
import subprocess
import tempfile
import tomllib
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
    """A scratch repository holding the tool, the probes the shipped fact file names, and the file."""
    root = tmp_path / "repo"
    facts = tomllib.loads((CHECKOUT / "facts" / "capabilities.toml").read_text())["facts"]
    probes = {fact["probe"] for fact in facts.values() if "probe" in fact}
    for name in ("tools/harness-facts", "facts/capabilities.toml", *sorted(probes)):
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(CHECKOUT / name, root / name)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    monkeypatch.chdir(root)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false",
                    "commit", "-q", "--no-verify", "-m", "base"], check=True)
    return root


def stage(root, text=None):
    path = root / "facts" / "capabilities.toml"
    if text is not None:
        path.write_text(text)
    subprocess.run(["git", "add", "facts/capabilities.toml"], cwd=root, check=True)
    return path


def test_a_broken_working_file_is_not_checked(repo):
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


def git(*args):
    subprocess.run(["git", *args], check=True, capture_output=True)


def point_reader_at(root, name):
    tool = root / "tools" / "harness-facts"
    tool.write_text(tool.read_text().replace('"facts" / "capabilities.toml"', f'"facts" / "{name}"'))
    git("add", "tools/harness-facts")


def test_a_staged_deletion_is_refused(repo, capsys):
    git("rm", "-q", "facts/capabilities.toml")
    assert load_hook().facts_check() == 1
    assert "facts/capabilities.toml: No such file" in capsys.readouterr().err


def test_a_deletion_from_the_index_alone_is_refused(repo, capsys):
    git("rm", "-q", "--cached", "facts/capabilities.toml")    # the working file still reads
    assert load_hook().facts_check() == 1
    assert "facts/capabilities.toml: No such file" in capsys.readouterr().err


def test_a_skip_worktree_entry_is_still_in_the_staged_tree(repo):
    git("update-index", "--skip-worktree", "facts/capabilities.toml")
    assert load_hook().facts_check() == 0


def test_messages_name_staged_paths_under_a_linked_tmpdir(repo, tmp_path, monkeypatch, capsys):
    real = tmp_path / "realtmp"
    real.mkdir()
    (tmp_path / "linktmp").symlink_to(real)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "linktmp"))
    git("rm", "-q", "--cached", "facts/capabilities.toml")
    assert load_hook().facts_check() == 1
    assert "harness-facts: facts/capabilities.toml: No such file" in capsys.readouterr().err
    assert not any(real.iterdir())                             # the export is removed


def test_a_held_index_lock_does_not_stop_the_check(repo):
    (repo / ".git" / "index.lock").write_text("")              # a concurrent `git status`
    assert load_hook().facts_check() == 0


def test_an_intent_to_add_probe_is_not_in_the_staged_tree(repo, capsys):
    text = (repo / "facts" / "capabilities.toml").read_text()
    probe = sorted(fact["probe"] for fact in tomllib.loads(text)["facts"].values() if "probe" in fact)[0]
    (repo / "agents" / "new-probe.sh").write_text("#!/bin/sh\n")
    git("add", "-N", "agents/new-probe.sh")                    # recorded, but the commit leaves it out
    stage(repo, text.replace(f'"{probe}"', '"agents/new-probe.sh"'))
    assert load_hook().facts_check() == 1
    assert "probe agents/new-probe.sh is not a file" in capsys.readouterr().err


def test_a_rename_without_the_reader_is_refused(repo, capsys):
    git("mv", "facts/capabilities.toml", "facts/moved.toml")
    assert load_hook().facts_check() == 1
    assert "facts/capabilities.toml: No such file" in capsys.readouterr().err


def test_a_reader_moved_without_its_file_is_refused(repo, capsys):
    point_reader_at(repo, "moved.toml")
    assert load_hook().facts_check() == 1
    assert "facts/moved.toml: No such file" in capsys.readouterr().err


def test_a_move_with_its_reader_passes(repo):
    git("mv", "facts/capabilities.toml", "facts/moved.toml")
    point_reader_at(repo, "moved.toml")
    assert load_hook().facts_check() == 0


def test_a_staged_reader_deletion_is_refused(repo, capsys):
    git("rm", "-q", "--cached", "tools/harness-facts")
    assert load_hook().facts_check() == 1
    assert "tools/harness-facts is not staged" in capsys.readouterr().err


def test_a_staged_probe_deletion_is_refused(repo, capsys):
    facts = tomllib.loads((repo / "facts" / "capabilities.toml").read_text())["facts"]
    probe = sorted(fact["probe"] for fact in facts.values() if "probe" in fact)[0]
    git("rm", "-q", "--cached", probe)
    assert load_hook().facts_check() == 1
    assert f"probe {probe} is not a file" in capsys.readouterr().err


def test_removed_mirror_command_is_refused(repo, capsys):
    assert load_hook().main(['facts-mirror']) == 1
    assert 'accepts no arguments' in capsys.readouterr().err
