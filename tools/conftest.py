"""Fixtures for the session-archive tests: a fake HOME holding every source root, and
an archive root with its marker. pytest puts tools/ on sys.path, so the package
imports by name."""
import pytest

from session_archive import config


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
