"""Exact indexed-byte proof through the real loader, live reads and archive read-back."""
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from session_archive import config
from session_archive.capture import capture_run
from session_archive.decide import is_transcript
from session_archive.inputs import claude_units, codex_units, load_obs_state
from session_archive.prune import Context, evaluate, prune_run
from session_archive.testing import claude_session, codex_rollout, obs_payload


def load(payload):
    return load_obs_state(("fixture-obs",), runner=lambda argv, **kwargs:
                          subprocess.CompletedProcess(argv, 0, json.dumps(payload), ""))


def make_world(home, archive, manifest, kind, *, capture=True):
    source = next(s for s in config.sources(home) if s.name == kind)
    path = claude_session(source.root) if kind == "claude" else codex_rollout(source.root)
    (unit,) = claude_units(source) if kind == "claude" else codex_units(source)
    payload = obs_payload(*(source.root / rel for rel in unit.files if is_transcript(kind, rel)))
    if capture:
        capture_run(archive, manifest, [source])
    ctx = Context(archive, manifest, load(payload), lambda: set(), time.time_ns(), "proof")
    return source, unit, path, payload, ctx


@pytest.fixture(params=["claude", "codex"])
def world(home, archive, manifest, request):
    return make_world(home, archive, manifest, request.param)


def test_complete_current_unit_is_eligible(world):
    _source, unit, _path, _payload, ctx = world
    assert evaluate(unit, ctx, set()) is None


def test_replaced_inode_with_equal_bytes_and_mtime_is_index_stale(world, tmp_path):
    _source, unit, path, _payload, ctx = world
    original = path.stat()
    replacement = tmp_path / "replacement"
    shutil.copy2(path, replacement)
    replacement.replace(path)
    current = path.stat()
    assert current.st_ino != original.st_ino
    assert (current.st_size, current.st_mtime_ns) == (original.st_size, original.st_mtime_ns)
    assert evaluate(unit, ctx, set()) == "index-stale"


@pytest.mark.parametrize("kind", ["claude", "codex"])
def test_preserved_stat_rewrite_is_index_stale(home, archive, manifest, kind):
    source, unit, path, _payload, ctx = make_world(home, archive, manifest, kind, capture=False)
    original, info = path.read_bytes(), path.stat()
    changed = original.replace(b"a", b"b", 1)
    assert changed != original and len(changed) == len(original)
    path.write_bytes(changed)
    os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
    assert path.stat().st_ino == info.st_ino
    capture_run(archive, manifest, [source])
    assert evaluate(unit, ctx, set()) == "index-stale"


@pytest.mark.parametrize("field", ["device", "indexed_span"])
def test_wrong_indexed_device_or_digest_is_index_stale(world, field):
    _source, unit, path, payload, ctx = world
    row = next(row for row in payload["files"] if row["path"] == str(path))
    if field == "device":
        row["device"] += 1
        row["observed"]["device"] = row["device"]
    else:
        row["indexed_span"]["sha256"] = "00" * 32
    ctx.obs = load(payload)
    assert evaluate(unit, ctx, set()) == "index-stale"


def test_unknown_harness_cannot_certify_a_known_source(world):
    _source, unit, path, payload, ctx = world
    row = next(row for row in payload["files"] if row["path"] == str(path))
    row.update(harness="future-harness", identity={"opaque": True})
    ctx.obs = load(payload)
    assert evaluate(unit, ctx, set()) == "index-stale"


def test_absent_transcript_evidence_is_unindexed(world):
    _source, unit, path, _payload, ctx = world
    del ctx.obs[str(path)]
    assert evaluate(unit, ctx, set()) == "unindexed"


def test_nonready_subagent_keeps_entire_claude_unit(home, archive, manifest):
    source, _unit, path, payload, ctx = make_world(home, archive, manifest, "claude")
    row = next(row for row in payload["files"] if "/subagents/" in row["path"])
    row.update(ready=False, not_ready=["extractors_stale"])
    ctx.obs = load(payload)
    report = {}
    assert prune_run(ctx, [source], apply=True, codex_probed=True, report=report)
    assert report["claude"]["totals"] == {"kept:index-stale": 1}
    assert path.exists() and Path(row["path"]).exists()
