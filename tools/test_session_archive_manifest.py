"""The manifest orders versions newest first, prefers the mirror on a tie, and keeps logs."""
from dataclasses import replace

from session_archive.manifest import MIRROR, Manifest, Run, Version

V = Version("claude", "p/s.jsonl", MIRROR, 10, 1, "aa", "2026-01-01T00:00:00.000000Z")


def test_put_and_read_back(manifest):
    manifest.put(V)
    assert manifest.mirror("claude", "p/s.jsonl") == V
    assert manifest.latest("claude", "p/s.jsonl") == V
    assert manifest.mirror("claude", "other") is None


def test_latest_is_newest_and_diverged_lists_it(manifest):
    manifest.put(V)
    newer = replace(V, location="versions/claude/p/s.jsonl@2026-02-01T00:00:00.000000Z", size=4,
                    sha256="bb", captured_at="2026-02-01T00:00:00.000000Z")
    manifest.put(newer)
    assert manifest.latest("claude", "p/s.jsonl") == newer
    assert manifest.rows("claude", "p/s.jsonl") == [newer, V]
    assert manifest.diverged() == [newer]


def test_tie_prefers_mirror(manifest):
    version = replace(V, location="versions/claude/p/s.jsonl@x")
    manifest.put(version)
    manifest.put(V)
    assert manifest.latest("claude", "p/s.jsonl") == V
    assert manifest.diverged() == []


def test_total_size_counts_every_stored_version(manifest):
    manifest.put(V)
    manifest.put(replace(V, location="versions/x", size=5))
    assert manifest.total_size() == 15


def test_runs_and_probe(manifest):
    manifest.record_run(Run("r1", "capture", "apply", "2026-01-01T00:00:00.000000Z",
                            "2026-01-01T00:01:00.000000Z", True, {"claude": {"copied": 1}}))
    manifest.record_run(Run("r2", "capture", "apply", "2026-01-02T00:00:00.000000Z",
                            "2026-01-02T00:01:00.000000Z", False, {}))
    assert manifest.last_run("capture").run_id == "r2"
    assert manifest.last_run("capture", ok_only=True).report == {"claude": {"copied": 1}}
    assert manifest.last_run("prune") is None
    assert not manifest.probe_passed("codex-cli 1.0")
    manifest.record_probe("codex-cli 1.0", "2026-01-01T00:00:00.000000Z")
    assert manifest.probe_passed("codex-cli 1.0")


def test_persists_across_open(archive):
    first = Manifest.open(archive)
    first.put(V)
    first.close()
    second = Manifest.open(archive)
    assert second.mirror("claude", "p/s.jsonl") == V
    second.close()
