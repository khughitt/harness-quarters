"""One case per prune condition (spec §3.4), over constructed records only."""
from dataclasses import replace

import pytest

from session_archive.decide import FileFacts, ObsFile, Stat, file_reason, is_transcript, unit_reason
from session_archive.manifest import MIRROR, Version

DAY = 86_400 * 10**9
NOW = 400 * DAY
OLD = NOW - 40 * DAY


def version(location=MIRROR, size=10, sha="a"):
    return Version("claude", "p/s.jsonl", location, size, OLD, sha, "2026-01-01T00:00:00.000000Z")


PASSING = FileFacts(
    relpath="p/s.jsonl", live=Stat(10, OLD), live_sha256="a", mirror=version(), latest=version(),
    mirror_sha256="a", transcript=True, obs=ObsFile(10, OLD // 1_000_000, 10, False, True, False),
    tail_has_newline=False, open=False)


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
    (dict(obs=ObsFile(10, OLD // 1_000_000, 10, False, True, True)), "unindexed"),
    (dict(obs=ObsFile(9, OLD // 1_000_000, 9, False, True, False)), "index-stale"),
    (dict(obs=ObsFile(10, OLD // 1_000_000, 10, False, False, False)), "index-stale"),
    (dict(obs=ObsFile(10, OLD // 1_000_000, 8, False, True, False)), "index-stale"),
    (dict(obs=ObsFile(10, OLD // 1_000_000, 8, True, True, False), tail_has_newline=True), "index-stale"),
    (dict(open=True), "open"),
])
def test_each_condition(change, reason):
    assert file_reason(replace(PASSING, **change), NOW) == reason


def test_diverged_latest_blocks_prune_even_when_live_matches_mirror():
    facts = replace(PASSING, latest=version(location="versions/x", size=11, sha="b"))
    assert file_reason(facts, NOW) == "diverged"


def test_partial_tail_without_newline_passes():
    facts = replace(PASSING, obs=ObsFile(10, OLD // 1_000_000, 8, True, True, False))
    assert file_reason(facts, NOW) is None


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
