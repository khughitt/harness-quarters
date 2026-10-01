"""The host gate refuses with exit 2 and a named cause; the archive lock refuses with 75."""
import fcntl
import os

import pytest

from session_archive import config
from session_archive.testing import run_tool, write_config


def test_sources_table_matches_spec(tmp_path):
    table = {s.name: (s.kind, s.root.relative_to(tmp_path).as_posix(), s.pruned)
             for s in config.sources(tmp_path)}
    assert table == {
        "claude": ("claude", ".claude/projects", True),
        "claude-work": ("claude", ".claude-work/projects", True),
        "codex": ("codex", ".codex/sessions", True),
        "codex-archived": ("codex", ".codex/archived_sessions", False),
        "codex-work": ("codex", ".codex-work/sessions", False),
    }


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
