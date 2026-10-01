"""Pure decisions: capture action and the extension check (spec §3.3)."""
from session_archive.decide import Stat, capture_action, extends
from session_archive.manifest import MIRROR, Version


def version(size=10, mtime_ns=5, sha="d", location=MIRROR):
    return Version("claude", "p/s.jsonl", location, size, mtime_ns, sha, "2026-01-01T00:00:00.000000Z")


def test_first_sight_copies():
    assert capture_action(Stat(10, 5), None, None) == "copy"


def test_changed_file_copies():
    assert capture_action(Stat(12, 6), version(), Stat(10, 5)) == "copy"


def test_unchanged_with_intact_copy_skips():
    assert capture_action(Stat(10, 5), version(), Stat(10, 5)) == "skip"


def test_unchanged_with_missing_or_damaged_copy_repairs():
    assert capture_action(Stat(10, 5), version(), None) == "repair"
    assert capture_action(Stat(10, 5), version(), Stat(3, 5)) == "repair"


def test_extends_without_mirror():
    assert extends(4, None, None)


def test_extends_when_prefix_matches_recorded_digest():
    assert extends(15, "d", version(size=10, sha="d"))
    assert extends(10, "d", version(size=10, sha="d"))


def test_does_not_extend_when_shorter_or_different():
    assert not extends(9, None, version(size=10, sha="d"))
    assert not extends(15, "x", version(size=10, sha="d"))
