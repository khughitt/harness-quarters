"""pre-commit validates the staged fact file and harness manifest as staged, not as they sit
in the working tree, and the filter config of the real repository."""
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import time
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


CLEAN_FILTER = ".githooks/harness-state-clean %f"
# Clean tracked configs: what the filter stages from them is their own bytes.
TRACKED = {
    "claude/settings.json": json.dumps({"theme": "dark-ansi"}, indent=2) + "\n",
    "codex/config.toml": "[features]\nhooks = true\n",
    "pi/settings.json": json.dumps({"theme": "system"}, indent=2) + "\n",
    "agy/settings.json": json.dumps({"allowNonWorkspaceAccess": True}, indent=2) + "\n",
}


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A scratch repository holding the fact reader, the probes the shipped fact file names,
    the file, the manifest checker and clean filter with the shipped harnesses.toml and
    .gitattributes, clean tracked configs, and the filter config `just setup` writes. The
    hook runs in this process and its git children inherit the process environment, so that
    environment is rebuilt key by key: HOME, XDG_CONFIG_HOME and the global git config under
    tmp_path, and no inherited GIT_* variable."""
    root = tmp_path / "repo"
    facts = tomllib.loads((CHECKOUT / "facts" / "capabilities.toml").read_text())["facts"]
    probes = {fact["probe"] for fact in facts.values() if "probe" in fact}
    for name in ("tools/harness-facts", "facts/capabilities.toml", "harnesses.toml", ".gitattributes",
                 ".githooks/harness_state.py", ".githooks/harness-state-clean", *sorted(probes)):
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(CHECKOUT / name, root / name)
    for name, text in TRACKED.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    home = tmp_path / "home"
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
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], check=True, text=True, capture_output=True)
    git_dir = subprocess.run(["git", "rev-parse", "--absolute-git-dir"], check=True, text=True,
                             capture_output=True)
    assert Path(top.stdout.strip()) == root.resolve()
    assert Path(git_dir.stdout.strip()).is_relative_to(root.resolve())
    subprocess.run(["git", "config", "filter.harness-state.clean", CLEAN_FILTER], check=True)
    subprocess.run(["git", "config", "filter.harness-state.required", "true"], check=True)
    subprocess.run(["git", "config", "filter.harness-state.smudge", "cat"], check=True)
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-q", "--no-verify", "-m", "base"], check=True)
    # Age the tracked configs so no index entry is racily clean: git rechecks a racy entry's
    # content through the required filter at every index write, and a test that stages a
    # broken harnesses.toml would then fail in the filter rather than reach the hook.
    past = time.time() - 60
    for name in TRACKED:
        os.utime(root / name, (past, past))
    subprocess.run(["git", "update-index", "-q", "--refresh"], check=True)
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



OVERLAP = """
[harnesses.extra.live_state]
config = "agy/settings-x.json"
filter_glob = "agy/settings-x*.json"
format = "json"
clean_keys = ["k"]
"""


def stage_manifest(old, new):
    path = Path("harnesses.toml")
    text = path.read_text()
    assert old in text
    path.write_text(text.replace(old, new, 1))
    git("add", "harnesses.toml")


def stage_attributes():
    path = Path(".gitattributes")
    path.write_text("".join(line for line in path.read_text().splitlines(keepends=True)
                            if not line.startswith("pi/")))
    git("add", ".gitattributes")


# Each case: how it breaks the staged tree or the filter config, and what stderr names.
STAGED_VIOLATIONS = {
    "bad-regex": (lambda: stage_manifest("'tui\\.model_availability_nux'", "'tui\\.model_(availability'"),
                  "not a valid regex"),
    "partition": (lambda: stage_manifest('unrestored_keys = ["deviceId", "trackingId"]',
                                         'unrestored_keys = ["deviceId"]'),
                  "pick_units plus unrestored_keys"),
    "overlap": (lambda: stage_manifest("[harnesses.opencode]", OVERLAP.lstrip() + "\n[harnesses.opencode]"),
                "overlaps"),
    "gitattributes-drift": (stage_attributes, ".gitattributes lacks `pi/settings*.json"),
    "required-unset": (lambda: git("config", "--unset", "filter.harness-state.required"),
                       "filter.harness-state.required"),
    "smudge-unset": (lambda: git("config", "--unset", "filter.harness-state.smudge"),
                     "filter.harness-state.smudge"),
    "manifest-deleted": (lambda: git("rm", "-q", "--cached", "harnesses.toml"), "harnesses.toml"),
    "checker-deleted": (lambda: git("rm", "-q", "--cached", ".githooks/harness_state.py"),
                        ".githooks/harness_state.py is not staged"),
    "facts-harness-undeclared": (lambda: stage_manifest("[harnesses.opencode]\n", ""), "opencode"),
}


@pytest.mark.parametrize("name", sorted(STAGED_VIOLATIONS))
def test_staged_live_state_and_gitattributes_violations_are_refused(repo, capsys, name):
    hook = load_hook()
    assert hook.staged_checks() == 0, capsys.readouterr().err
    capsys.readouterr()
    breaks, named = STAGED_VIOLATIONS[name]
    breaks()
    if name != "facts-harness-undeclared":        # the fact reader alone refuses that one
        assert hook.manifest_check() == 1
        err = capsys.readouterr().err
        assert named in err, err
        assert "staged-tree-" not in err, err      # no temp-tree path prefix
    assert hook.staged_checks() == 1
    err = capsys.readouterr().err
    assert named in err, err
    assert "staged-tree-" not in err, err
    assert "Traceback" not in err, err


def test_already_leaked_staged_settings_blob_is_refused_until_renormalized(repo, capsys):
    for key in ("required", "clean", "smudge"):
        git("config", "--unset", f"filter.harness-state.{key}")
    Path("pi/settings.json").write_text(json.dumps({"theme": "system", "deviceId": "leaked-id"}, indent=2) + "\n")
    git("add", "pi/settings.json")                  # no filter ran: the raw blob is staged
    assert "leaked-id" in subprocess.run(["git", "show", ":pi/settings.json"], check=True, text=True,
                                         capture_output=True).stdout
    git("config", "filter.harness-state.clean", CLEAN_FILTER)    # then just setup runs
    git("config", "filter.harness-state.required", "true")
    git("config", "filter.harness-state.smudge", "cat")
    hook = load_hook()
    assert hook.manifest_check() == 1
    err = capsys.readouterr().err
    assert "pi/settings.json" in err and "git add --renormalize pi/settings.json" in err, err
    assert hook.staged_checks() == 1
    capsys.readouterr()

    git("add", "--renormalize", "pi/settings.json")

    assert hook.manifest_check() == 0, capsys.readouterr().err
    assert hook.staged_checks() == 0, capsys.readouterr().err
    staged = subprocess.run(["git", "show", ":pi/settings.json"], check=True, text=True,
                            capture_output=True).stdout
    assert "leaked-id" not in staged and json.loads(staged) == {"theme": "system"}
