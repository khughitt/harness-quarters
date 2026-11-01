"""The host gate refuses with exit 2 and a named cause; the archive lock refuses with 75."""
import fcntl
import os
from pathlib import Path

import pytest

import harness_stores

import harness_stores
from session_archive import config
from session_archive.testing import run_tool, write_config


def test_sources_table_matches_spec(tmp_path):
    table = {s.name: (s.harness, s.home.relative_to(tmp_path).as_posix(),
                      s.root.relative_to(tmp_path).as_posix(), s.prune is not None,
                      s.required, s.append_only)
             for s in harness_stores.archive_sources(tmp_path)}
    assert table == {
        "claude": ("claude-code", ".claude", ".claude/projects", True, True, True),
        "claude-work": ("claude-code", ".claude-work", ".claude-work/projects", True, True, True),
        "codex": ("codex", ".codex", ".codex/sessions", True, True, True),
        "codex-archived": ("codex", ".codex", ".codex/archived_sessions", False, True, True),
        "codex-work": ("codex", ".codex-work", ".codex-work/sessions", False, True, True),
    }


def test_no_kind_branches_remain():
    package = Path(config.__file__).parent
    for name in ("prune.py", "decide.py", "inputs.py"):
        text = (package / name).read_text()
        assert 'kind == "claude"' not in text and 'kind == "codex"' not in text, name
        assert ".kind ==" not in text, name


def test_unconfigured_host_exits_2(home):
    result = run_tool("capture", home=home)
    assert result.returncode == 2
    assert "not configured on this host" in result.stderr


def test_missing_archive_root_exits_2(home, tmp_path):
    write_config(home, tmp_path / "absent")
    result = run_tool("capture", home=home)
    assert result.returncode == 2
    assert "does not exist" in result.stderr


def test_missing_marker_exits_2(home, tmp_path):
    bare = tmp_path / "bare"
    bare.mkdir()
    write_config(home, bare)
    result = run_tool("capture", home=home)
    assert result.returncode == 2
    assert "lacks the marker file" in result.stderr


def test_missing_source_root_exits_2(home, archive):
    write_config(home, archive)
    (home / ".codex-work" / "sessions").rmdir()
    result = run_tool("capture", home=home)
    assert result.returncode == 2
    assert "source root missing" in result.stderr


@pytest.mark.parametrize("line", ['obs_command = []', 'obs_command = "obs"', ''])
def test_bad_obs_command_is_refused(tmp_path, archive, line):
    path = tmp_path / "config.toml"
    path.write_text(f'archive_root = "{archive}"\n{line}\n')
    with pytest.raises(config.HostGateError):
        config.load_config(path)


def test_uninspectable_ok_is_optional_and_typed(tmp_path, archive):
    path = tmp_path / "config.toml"
    base = f'archive_root = "{archive}"\nobs_command = ["obs"]\n'
    path.write_text(base)
    assert config.load_config(path).uninspectable_ok == ()
    path.write_text(base + 'uninspectable_ok = ["(sd-pam)"]\n')
    assert config.load_config(path).uninspectable_ok == ("(sd-pam)",)
    path.write_text(base + 'uninspectable_ok = "(sd-pam)"\n')
    with pytest.raises(config.HostGateError):
        config.load_config(path)


def test_held_lock_exits_75(home, archive):
    write_config(home, archive)
    fd = os.open(archive / ".lock", os.O_RDWR | os.O_CREAT)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        result = run_tool("capture", home=home)
    finally:
        os.close(fd)
    assert result.returncode == 75
    assert "holds" in result.stderr


@pytest.mark.parametrize("content, message", [
    ('archive_root = [\n', "cannot read configuration"),
    ('archive_root = 42\nobs_command = ["obs"]\n', "archive_root must be a string"),
])
def test_invalid_config_exits_2(home, archive, content, message):
    path = write_config(home, archive)
    path.write_text(content)
    result = run_tool("capture", home=home)
    assert result.returncode == 2
    assert str(path) in result.stderr
    assert message in result.stderr
    assert "Traceback" not in result.stderr


def test_config_read_error_exits_2(home, archive, monkeypatch, capsys):
    from session_archive import cli

    path = write_config(home, archive)

    def unreadable(self):
        raise PermissionError("permission denied reading configuration")

    monkeypatch.setattr(type(path), "read_text", unreadable)
    assert cli.main(["capture"]) == 2
    error = capsys.readouterr().err
    assert str(path) in error
    assert "permission denied reading configuration" in error
    assert "Traceback" not in error


def test_invalid_config_encoding_exits_2(home, archive):
    path = write_config(home, archive)
    path.write_bytes(b"\xff")
    result = run_tool("capture", home=home)
    assert result.returncode == 2
    assert str(path) in result.stderr
    assert "cannot read configuration" in result.stderr
    assert "Traceback" not in result.stderr


def source_at(tmp_path, name="x", required=False, root_name="root"):
    from session_archive.config import Source
    home = tmp_path / "h"
    home.mkdir(exist_ok=True)
    return Source(name, name, home, home / root_name, None, required=required)


def test_optional_source_with_absent_root_is_skipped_when_never_captured(tmp_path):
    source = source_at(tmp_path)
    assert config.check_sources([source], lambda name: False) == {"x": "root absent, never captured"}


def test_optional_source_with_absent_root_aborts_once_captured(tmp_path):
    source = source_at(tmp_path)
    with pytest.raises(config.HostGateError, match=str(source.root)):
        config.check_sources([source], lambda name: True)


def test_required_source_with_absent_root_still_aborts(tmp_path):
    source = source_at(tmp_path, required=True)
    with pytest.raises(config.HostGateError, match="missing"):
        config.check_sources([source], lambda name: False)


def test_present_optional_source_does_not_ask_captured(tmp_path):
    source = source_at(tmp_path)
    source.root.mkdir()

    def captured(name):
        raise AssertionError("captured must not be called")
    assert config.check_sources([source], captured) == {}


def test_symlinked_home_aborts(tmp_path):
    from session_archive.config import Source
    real = tmp_path / "real"
    (real / "root").mkdir(parents=True)
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    source = Source("x", "x", link, link / "root", None)
    with pytest.raises(config.HostGateError, match="symlink"):
        config.check_sources([source], lambda name: False)
