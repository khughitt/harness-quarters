"""One case per prune condition (spec §3.4), over constructed records only."""
from dataclasses import replace

import pytest

from session_archive.decide import FileFacts, ObsFile, Stat, file_reason, is_transcript, unit_reason
from session_archive.manifest import MIRROR, Version
from session_archive.testing import TID

DAY = 86_400 * 10**9
NOW = 400 * DAY
OLD = NOW - 40 * DAY


def version(location=MIRROR, size=10, sha="a"):
    return Version("claude", "p/s.jsonl", location, size, OLD, sha, "2026-01-01T00:00:00.000000Z")


INDEXED = ObsFile(size=10, mtime_ms=OLD // 1_000_000, byte_offset=10, partial_tail=False,
                  schema_current=True, missing=False, harness="claude-code", device=1, inode=2,
                  ready=True, not_ready=(), span_length=10, span_sha256="a", thread_id=None,
                  filename_id=None, identity_conflicts=())
PASSING = FileFacts(
    relpath="p/s.jsonl", live=Stat(10, OLD), live_sha256="a", mirror=version(), latest=version(),
    mirror_sha256="a", transcript=True, obs=INDEXED, open=False,
    device=1, inode=2, harness="claude-code", thread_id=None)


def test_passing_file():
    assert file_reason(PASSING, NOW) is None


@pytest.mark.parametrize("change, reason", [
    (dict(live=Stat(10, NOW - 29 * DAY)), "active"),
    (dict(latest=version(location="versions/x", sha="b"), mirror=version(size=4)), "diverged"),
    (dict(mirror=None, latest=None), "uncaptured"),
    (dict(live_sha256="b"), "uncaptured"),
    (dict(mirror_sha256="z"), "archive-damaged"),
    (dict(mirror_sha256=None), "archive-damaged"),
    (dict(obs=None), "unindexed"),
    (dict(obs=replace(INDEXED, missing=True)), "unindexed"),
    (dict(obs=replace(INDEXED, size=9, byte_offset=9)), "index-stale"),
    (dict(obs=replace(INDEXED, schema_current=False)), "index-stale"),
    (dict(obs=replace(INDEXED, byte_offset=8)), "index-stale"),
    (dict(obs=replace(INDEXED, byte_offset=8, partial_tail=True)), "index-stale"),
    (dict(open=True), "open"),
])
def test_each_condition(change, reason):
    assert file_reason(replace(PASSING, **change), NOW) == reason


def test_diverged_latest_blocks_prune_even_when_live_matches_mirror():
    facts = replace(PASSING, latest=version(location="versions/x", size=11, sha="b"))
    assert file_reason(facts, NOW) == "diverged"


def test_partial_tail_without_newline_is_kept():
    facts = replace(PASSING, obs=replace(INDEXED, byte_offset=8, partial_tail=True))
    assert file_reason(facts, NOW) == "index-stale"


@pytest.mark.parametrize("change", [
    {"ready": False}, {"not_ready": ("future_reason",)}, {"device": 3}, {"inode": 3},
    {"harness": "future-harness"}, {"span_length": 9}, {"span_sha256": "b"},
])
def test_strict_evidence_must_match_live(change):
    assert file_reason(replace(PASSING, obs=replace(INDEXED, **change)), NOW) == "index-stale"


@pytest.mark.parametrize("change", [
    {"thread_id": None}, {"filename_id": None}, {"thread_id": "other"},
    {"filename_id": "other"}, {"identity_conflicts": ("other",)},
])
def test_strict_codex_identity_must_match_filename(change):
    indexed = replace(INDEXED, harness="codex", thread_id=TID, filename_id=TID)
    facts = replace(PASSING, harness="codex", thread_id=TID, obs=replace(indexed, **change))
    assert file_reason(facts, NOW) == "index-stale"


def test_matching_codex_identity_passes():
    indexed = replace(INDEXED, harness="codex", thread_id=TID, filename_id=TID)
    assert file_reason(replace(PASSING, harness="codex", thread_id=TID, obs=indexed), NOW) is None


def test_non_transcript_needs_no_index():
    assert file_reason(replace(PASSING, transcript=False, obs=None), NOW) is None


def test_unit_takes_first_failure_and_keeps_empty():
    assert unit_reason([PASSING, replace(PASSING, open=True), replace(PASSING, obs=None)], NOW) == "open"
    assert unit_reason([PASSING], NOW) is None
    assert unit_reason([], NOW) == "empty"


@pytest.mark.parametrize("kind, rel, expected", [
    ("claude", "p/s.jsonl", True),
    ("claude", "p/s/subagents/agent-1.jsonl", True),
    ("claude", "p/s/tool-results/r.txt", False),
    ("claude", "p/s/tool-results/r.jsonl", False),
    ("codex", "2026/01/01/rollout-x.jsonl", True),
    ("codex", "2026/01/01/notes.txt", False),
])
def test_is_transcript(kind, rel, expected):
    assert is_transcript(kind, rel) is expected
