"""probe-codex checks the Codex behaviour the protocol relies on (spec §3.4.3, §5)."""
import json
import os
import subprocess
import sys

from session_archive import prune
from session_archive.manifest import Manifest
from session_archive.probe import codex_version, probe_codex
from session_archive.testing import lenient_open_inodes, run_tool, uninspectable_comms, write_config


def test_codex_stub_children_use_minimal_environment(stub_codex, tmp_path, home, monkeypatch):
    allowed = {"PATH", "HOME", "USER", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME",
               "CODEX_HOME", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "STUB_CODEX_MODE",
               "STUB_CODEX_LOG", "STUB_CODEX_VERSION", "STUB_CODEX_WRITER_SECONDS",
               "PYTEST_CURRENT_TEST", "LC_ALL"}
    real_run, real_popen = subprocess.run, subprocess.Popen
    seen = []

    def inspect(environment):
        if environment is None:
            return
        unexpected = set(environment) - allowed
        assert not unexpected
        assert environment["HOME"] == str(home)
        assert environment["USER"] == "test"
        assert environment["OPENAI_API_KEY"] == "test-invalid"
        assert environment["ANTHROPIC_API_KEY"] == "test-invalid"
        assert environment["STUB_CODEX_VERSION"] == "codex-cli 9.9.9"
        seen.append(True)

    def run(*args, **kwargs):
        inspect(kwargs.get("env"))
        return real_run(*args, **kwargs)

    def popen(*args, **kwargs):
        inspect(kwargs.get("env"))
        return real_popen(*args, **kwargs)

    monkeypatch.setenv("STUB_CODEX_VERSION", "codex-cli 9.9.9")
    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(subprocess, "Popen", popen)
    native = subprocess.run([sys.executable, "-c", (
        "import json,os; print(json.dumps({'keys': sorted(os.environ), "
        "'fake': os.environ.get('OPENAI_API_KEY') == 'test-invalid', "
        "'home': os.environ.get('HOME')}))")], capture_output=True, text=True, check=True)
    observed = json.loads(native.stdout)
    assert not (set(observed["keys"]) - allowed)
    assert observed["fake"] and observed["home"] == str(home)
    assert codex_version(str(stub_codex)) == "codex-cli 9.9.9"
    result = probe_codex(str(stub_codex), tmp_path / "work", lenient_open_inodes)
    assert result.passed
    assert prune.run_codex_delete(str(stub_codex), home / ".codex", "test-thread", 5)
    assert seen


def test_probe_passes_against_conforming_codex(stub_codex, tmp_path):
    result = probe_codex(str(stub_codex), tmp_path / "work", lenient_open_inodes)
    assert result.passed, result.checks
    assert result.version == "codex-cli 0.0.0-stub"
    assert result.checks == {
        "thread_created": True,
        "writer_holds_lock": True,
        "writer_holds_rollout_open": True,
        "resume_refused_while_locked": True,
        "delete_refused_while_locked": True,
        "archive_moved": True,
        "archived_delete_removed_file": True,
        "archived_delete_removed_row": True,
    }


def test_probe_fails_when_lock_is_ignored(stub_codex, tmp_path, monkeypatch):
    monkeypatch.setenv("STUB_CODEX_MODE", "ignore-lock")
    result = probe_codex(str(stub_codex), tmp_path / "work", lenient_open_inodes)
    assert not result.passed
    assert result.checks["resume_refused_while_locked"] is False
    assert result.checks["delete_refused_while_locked"] is False


def test_probe_fails_when_writer_does_not_hold_its_rollout(stub_codex, tmp_path, monkeypatch):
    monkeypatch.setenv("STUB_CODEX_MODE", "writer-closes")
    result = probe_codex(str(stub_codex), tmp_path / "work", lenient_open_inodes)
    assert not result.passed
    assert result.checks["writer_holds_lock"] is True
    assert result.checks["writer_holds_rollout_open"] is False


def test_codex_version(stub_codex, monkeypatch):
    monkeypatch.setenv("STUB_CODEX_VERSION", "codex-cli 9.9.9")
    assert codex_version(str(stub_codex)) == "codex-cli 9.9.9"


def test_probe_isolates_every_codex_invocation(stub_codex, tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "caller-home"))
    work = tmp_path / "work"
    result = probe_codex(str(stub_codex), work, lenient_open_inodes)
    assert result.passed, result.checks
    calls = [json.loads(line) for line in (tmp_path / "codex.log").read_text().splitlines()]
    assert calls[0]["argv"] == ["--version"]
    assert all(call["codex_home"] == str(work / "home") for call in calls)


def test_probe_requires_row_before_archived_delete(stub_codex, tmp_path, monkeypatch):
    monkeypatch.setenv("STUB_CODEX_MODE", "no-thread-row")
    result = probe_codex(str(stub_codex), tmp_path / "work", lenient_open_inodes)
    assert not result.passed
    assert result.checks["archive_moved"] is True
    assert result.checks["archived_delete_removed_file"] is True
    assert result.checks["archived_delete_removed_row"] is False


def test_probe_command_records_passing_version(home, archive, stub_codex):
    write_config(home, archive, uninspectable_ok=uninspectable_comms())
    result = run_tool("probe-codex", home=home)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["passed"] is True
    opened = Manifest.open(archive)
    assert opened.probe_passed("codex-cli 0.0.0-stub")
    opened.close()
