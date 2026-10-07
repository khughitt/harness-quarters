"""The pure parts of rename-hq-steps; the rehearsal runs the rest against clones."""
import importlib.machinery
import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parent / "rename-hq-steps"


def load_steps():
    loader = importlib.machinery.SourceFileLoader("rename_hq_steps", str(TOOL))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(module)
    return module


def test_replace_once_replaces_text_found_exactly_once(tmp_path):
    steps = load_steps()
    path = tmp_path / "README.md"
    path.write_text("# tack\n\nserved by tack's links\n")
    steps.replace_once(path, "tack's links", "hq's links")
    assert path.read_text() == "# tack\n\nserved by hq's links\n"


@pytest.mark.parametrize("text", ["nothing here\n", "tack's links and tack's links\n"])
def test_replace_once_refuses_text_that_is_missing_or_repeated(tmp_path, text):
    steps = load_steps()
    path = tmp_path / "README.md"
    path.write_text(text)
    with pytest.raises(steps.Stop, match=r"README.md: expected exactly one \"tack's links\""):
        steps.replace_once(path, "tack's links", "hq's links")
    assert path.read_text() == text


def test_trust_text_appends_a_copy_of_the_old_table_to_the_saved_copy():
    steps = load_steps()
    saved = '[projects."/elsewhere"]\ntrust_level = "trusted"\n\n[projects."/s/tack"]\ntrust_level = "trusted"\n'
    assert steps.trust_text(saved, "/s/tack", "/s/hq") == saved + '\n[projects."/s/hq"]\ntrust_level = "trusted"\n'


def test_trust_text_leaves_a_trusted_new_path_alone():
    steps = load_steps()
    text = '[projects."/s/tack"]\ntrust_level = "trusted"\n\n[projects."/s/hq"]\ntrust_level = "trusted"\n'
    assert steps.trust_text(text, "/s/tack", "/s/hq") == text


def test_trust_text_has_nothing_to_copy_without_the_old_table():
    steps = load_steps()
    assert steps.trust_text('[projects."/elsewhere"]\ntrust_level = "trusted"\n', "/s/tack", "/s/hq") is None


def test_add_trust_keeps_what_git_stages_when_a_table_ends_the_live_config(tmp_path):
    """The live config ends with a non-trust table: an appended trust table would leave a
    blank line the clean filter keeps. Through codex-trust restore it does not."""
    steps = load_steps()
    repo = tmp_path / "tack"
    (repo / ".githooks").mkdir(parents=True)
    for name in ("codex-trust", "harness-state-clean"):
        shutil.copy2(TOOL.parent.parent / ".githooks" / name, repo / ".githooks" / name)
    git = ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run([*git, "config", "filter.harness-state.clean", ".githooks/harness-state-clean %f"], check=True)
    (repo / ".gitattributes").write_text("codex/config*.toml filter=harness-state\n")
    (repo / ".gitignore").write_text("local/\n")
    (repo / "codex").mkdir()
    config = repo / "codex" / "config.toml"
    config.write_text(f'model = "m"\n\n[projects."{repo}"]\ntrust_level = "trusted"\n\n[tui]\nx = 1\n')
    config.chmod(0o600)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-qm", "init"], check=True)
    assert subprocess.run([*git, "diff", "--quiet"]).returncode == 0
    (repo / "local" / "codex").mkdir(parents=True)
    new = tmp_path / "hq"
    steps.add_trust(repo, repo, new, require=True)
    assert f'[projects."{new}"]' in config.read_text() and f'[projects."{repo}"]' in config.read_text()
    assert f'[projects."{new}"]' in (repo / "local" / "codex" / "trust.toml").read_text()
    assert subprocess.run([*git, "diff", "--quiet"]).returncode == 0


def test_second_host_refuses_without_its_pre_move_record(tmp_path):
    (tmp_path / "cfg" / "tasks").mkdir(parents=True)
    (tmp_path / "cfg" / "tasks" / "projects.toml").write_text(f'[projects]\ntack = "{tmp_path / "tack"}"\n')
    root = tmp_path / "hq"
    (root / "tasks").mkdir(parents=True)
    (root / "tasks" / ".config.toml").write_text('prefix = "hq"\n')
    env = {**os.environ, "XDG_CONFIG_HOME": str(tmp_path / "cfg"), "HOME": str(tmp_path)}
    result = subprocess.run([str(TOOL), "second-host", "--root", str(root), "--state", str(tmp_path / "s.json")],
                            text=True, capture_output=True, env=env)
    assert result.returncode == 1 and "no record at" in result.stderr and "second-host-record" in result.stderr
    assert (tmp_path / "cfg" / "tasks" / "projects.toml").read_text() == f'[projects]\ntack = "{tmp_path / "tack"}"\n'


def test_second_host_record_refuses_a_root_that_is_not_the_old_project(tmp_path):
    root = tmp_path / "tack"
    (root / "tasks").mkdir(parents=True)
    (root / "tasks" / ".config.toml").write_text('prefix = "hq"\n')
    result = subprocess.run([str(TOOL), "second-host-record", "--root", str(root), "--state", str(tmp_path / "s.json")],
                            text=True, capture_output=True,
                            env={**os.environ, "XDG_CONFIG_HOME": str(tmp_path / "cfg"), "HOME": str(tmp_path)})
    assert result.returncode == 1 and "has the prefix 'hq', not 'tack'" in result.stderr
    assert not (tmp_path / "s.json").exists()


def test_second_host_refuses_before_the_sync_has_carried_the_rename(tmp_path):
    root = tmp_path / "hq"
    (root / "tasks").mkdir(parents=True)
    (root / "tasks" / ".config.toml").write_text('prefix = "tack"\n')
    result = subprocess.run([str(TOOL), "second-host", "--root", str(root), "--state", str(tmp_path / "s.json")],
                            text=True, capture_output=True,
                            env={**os.environ, "XDG_CONFIG_HOME": str(tmp_path / "cfg"), "HOME": str(tmp_path)})
    assert result.returncode == 1 and "has the prefix 'tack', not 'hq'" in result.stderr


def test_apply_edits_writes_nothing_when_a_later_edit_refuses(tmp_path):
    """A table stops before its first write: a refusal leaves the repository as save found it,
    so a corrected table can be rerun instead of rolling the whole cutover back."""
    steps = load_steps()
    (tmp_path / "a.md").write_text("tack's links\n")
    (tmp_path / "b.md").write_text("tack's links twice, tack's links\n")
    with pytest.raises(steps.Stop, match=r"b.md: expected exactly one"):
        steps.apply_edits(tmp_path, [("a.md", "tack's links", "hq's links"), ("b.md", "tack's links", "hq's links")])
    assert (tmp_path / "a.md").read_text() == "tack's links\n"
    assert (tmp_path / "b.md").read_text() == "tack's links twice, tack's links\n"


def test_apply_edits_applies_edits_to_one_file_in_table_order(tmp_path):
    steps = load_steps()
    (tmp_path / "a.md").write_text("# tack\n\ntack's links\n")
    steps.apply_edits(tmp_path, [("a.md", "# tack\n", "# hq\n"), ("a.md", "tack's links", "hq's links")])
    assert (tmp_path / "a.md").read_text() == "# hq\n\nhq's links\n"
