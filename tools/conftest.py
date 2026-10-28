"""Fixtures for the session-archive tests: a fake HOME holding every source root, and
an archive root with its marker. pytest puts tools/ on sys.path, so the package
imports by name."""
import os

import pytest

from session_archive import config
from session_archive.manifest import Manifest
from session_archive.testing import STUB_CODEX


@pytest.fixture
def home(tmp_path, monkeypatch):
    path = tmp_path / "home"
    for source in config.sources(path):
        source.root.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(path))
    return path


@pytest.fixture
def archive(tmp_path):
    root = tmp_path / "archive"
    root.mkdir()
    (root / config.MARKER).touch()
    return root


@pytest.fixture
def manifest(archive):
    opened = Manifest.open(archive)
    yield opened
    opened.close()


@pytest.fixture
def stub_codex(tmp_path, monkeypatch, home):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "codex"
    stub.write_text(STUB_CODEX)
    stub.chmod(0o755)
    environment = {
        "PATH": f"{bin_dir}{os.pathsep}{os.defpath}", "HOME": str(home), "USER": "test",
        "LC_ALL": "C.UTF-8",
        "XDG_CONFIG_HOME": str(home / ".config"), "XDG_DATA_HOME": str(home / ".local/share"),
        "XDG_STATE_HOME": str(home / ".local/state"), "CODEX_HOME": str(home / ".codex"),
        "OPENAI_API_KEY": "test-invalid", "ANTHROPIC_API_KEY": "test-invalid",
        "STUB_CODEX_MODE": "ok", "STUB_CODEX_LOG": str(tmp_path / "codex.log"),
        "STUB_CODEX_VERSION": "codex-cli 0.0.0-stub", "STUB_CODEX_WRITER_SECONDS": "1",
    }
    # Keep the native environment synchronized for children launched with env=None.
    for key in tuple(os.environ):
        monkeypatch.delenv(key)
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    return stub
