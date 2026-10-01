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
def stub_codex(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "codex"
    stub.write_text(STUB_CODEX)
    stub.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("STUB_CODEX_LOG", str(tmp_path / "codex.log"))
    return stub
