"""Claude successor links into an older unit under prune (spec §3.2-3.4).

Claude Code hands a running background agent to its successor session as a symlink,
<new>/subagents/agent-<id>.jsonl -> <old>/subagents/agent-<id>.jsonl. These cases pin
what the current protocol does with such a pair: where the link breaks, what happens to
the linking unit itself, and which link changes a retention check could still miss.
Assertions marked "current" record behaviour the retention rule is expected to change."""
import os
import time
from pathlib import Path

import pytest

from session_archive import config
from session_archive.capture import capture_run, mirror_path
from session_archive.prune import Context, Hooks, LeftoverQuarantine, prune_run
from session_archive.quarantine import QUARANTINE
from session_archive.testing import SID, claude_session, lenient_open_inodes, obs_for, write

OLD = SID
NEW = "22222222-2222-4333-8444-555555555555"  # sorts after OLD, so prune visits OLD first
AGENT = "subagents/agent-1.jsonl"


def link_path(src, sid=NEW) -> Path:
    return src.root / "-p" / sid / AGENT


def target_path(src) -> Path:
    return src.root / "-p" / OLD / AGENT


def quarantined(src, sid) -> Path:
    """Where delete_claude_unit puts a unit's <sid>/ directory in run1."""
    return src.home / QUARANTINE / "run1" / "-p" / sid / sid


def make_pair(src, old_age=40, new_age=1, absolute=False) -> Path:
    """An older unit holding a subagent transcript and a younger unit linking to it."""
    claude_session(src.root, age_days=old_age, sid=OLD)
    write(src.root / "-p" / f"{NEW}.jsonl", b'{"b":1}\n', new_age)
    link = link_path(src)
    link.parent.mkdir(parents=True)
    link.symlink_to(target_path(src) if absolute else Path("..", "..", OLD, AGENT))
    return link


def context(src, archive, manifest, hooks=None) -> Context:
    capture_run(archive, manifest, [src])
    transcripts = [p for p in (src.root / "-p").rglob("*.jsonl") if not p.is_symlink() and p.exists()]
    return Context(archive, manifest, obs_for(*transcripts), lenient_open_inodes, time.time_ns(), "run1",
                   hooks=hooks or Hooks())


@pytest.fixture
def src(home):
    return next(s for s in config.sources(home) if s.name == "claude")


def outcomes(report) -> dict[str, str]:
    return {entry["unit"]: entry["outcome"] for entry in report["claude"]["units"]}


def test_dry_run_offers_linked_target_and_is_silent_about_the_link(src, archive, manifest):
    link = make_pair(src)
    report = {}
    assert prune_run(context(src, archive, manifest), [src], apply=False, codex_probed=False, report=report)
    assert outcomes(report) == {f"-p/{OLD}": "eligible"}  # current: the incoming link is not seen
    assert report["claude"]["totals"] == {"eligible": 1, "kept:active": 1}
    assert link.exists()


@pytest.mark.parametrize("absolute", [False, True], ids=["relative", "absolute"])
def test_link_breaks_at_quarantine_and_stays_broken(src, archive, manifest, absolute):
    link = make_pair(src, absolute=absolute)
    seen = []
    hooks = Hooks(after_precheck=lambda u: seen.append(("precheck", link.exists())),
                  after_quarantine=lambda u: seen.append(("quarantine", link.exists())),
                  before_delete=lambda u: seen.append(("delete", link.exists())))
    report = {}
    assert prune_run(context(src, archive, manifest, hooks), [src], apply=True, codex_probed=False, report=report)
    assert outcomes(report) == {f"-p/{OLD}": "pruned"}
    assert seen == [("precheck", True), ("quarantine", False), ("delete", False)]  # current
    assert link.is_symlink() and not link.exists()  # current: a live unit holds a dangling link
    assert mirror_path(archive, "claude", f"-p/{OLD}/{AGENT}").read_bytes() == b'{"sub":1}\n'


def test_restored_target_relinks(src, archive, manifest):
    link = make_pair(src)
    handles, seen = [], []

    def hold(u):
        seen.append(link.exists())
        handles.append(open(quarantined(src, OLD) / AGENT, "rb"))

    report = {}
    try:
        prune_run(context(src, archive, manifest, Hooks(after_quarantine=hold)), [src], apply=True,
                  codex_probed=False, report=report)
    finally:
        for handle in handles:
            handle.close()
    assert outcomes(report) == {f"-p/{OLD}": "kept:open"}
    assert seen == [False] and link.exists()  # broken while quarantined, whole again on restore


def test_recreated_target_keeps_link_broken_until_a_person_merges(src, archive, manifest):
    link = make_pair(src)
    recreated = src.root / "-p" / f"{OLD}.jsonl"
    report = {}
    prune_run(context(src, archive, manifest, Hooks(after_quarantine=lambda u: recreated.write_bytes(b"{}\n"))),
              [src], apply=True, codex_probed=False, report=report)
    assert outcomes(report) == {f"-p/{OLD}": "failed:recreated"}
    assert not link.exists()  # the subagent transcript stays in quarantine with the unit
    with pytest.raises(LeftoverQuarantine):
        prune_run(context(src, archive, manifest), [src], apply=False, codex_probed=False, report={})


@pytest.mark.parametrize("absolute", [False, True], ids=["relative", "absolute"])
@pytest.mark.parametrize("target", ["retained", "pruned-same-run", "already-dangling"])
def test_linking_unit_strands_its_link_in_quarantine(src, archive, manifest, target, absolute):
    """The linking unit's own prune: eligibility ignores the link, and the link never reaches
    release, so the unit's directory cannot be emptied."""
    old_age = 1 if target == "retained" else 40
    link = make_pair(src, old_age=old_age, new_age=40, absolute=absolute)
    written = os.readlink(link)
    if target == "already-dangling":  # Claude's own cleanup took the older unit first
        for path in (src.root / "-p" / f"{OLD}.jsonl", src.root / "-p" / OLD):
            os.rename(path, src.home / path.name)
    ctx = context(src, archive, manifest)
    dry = {}
    assert prune_run(ctx, [src], apply=False, codex_probed=False, report=dry)
    assert outcomes(dry)[f"-p/{NEW}"] == "eligible"  # current: the dry-run review sees nothing amiss
    report = {}
    ok = prune_run(ctx, [src], apply=True, codex_probed=False, report=report)
    expected = {f"-p/{NEW}": "failed:release"}
    if target == "pruned-same-run":
        expected[f"-p/{OLD}"] = "pruned"
    assert not ok and outcomes(report) == expected  # current
    stranded = quarantined(src, NEW) / AGENT
    assert stranded.is_symlink() and os.readlink(stranded) == written
    assert not (src.root / "-p" / f"{NEW}.jsonl").exists()  # current: regular files released first
    assert not link.is_symlink()
    if target == "retained":
        # Never followed: the absolute link still reaches O from quarantine, and O is intact.
        assert stranded.exists() == absolute
        assert target_path(src).read_bytes() == b'{"sub":1}\n'
    with pytest.raises(LeftoverQuarantine):  # current: one linking unit stops every later prune
        prune_run(context(src, archive, manifest), [src], apply=False, codex_probed=False, report={})


@pytest.mark.parametrize("stage", ["after_precheck", "after_quarantine", "before_delete"])
def test_link_created_during_the_protocol_is_not_noticed(src, archive, manifest, stage):
    """No link at pre-check; a successor links into the older unit at a protocol seam."""
    claude_session(src.root, sid=OLD)
    write(src.root / "-p" / f"{NEW}.jsonl", b'{"b":1}\n', 1)
    link = link_path(src)
    resolved = []

    def create(u):
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(Path("..", "..", OLD, AGENT))
        resolved.append(link.exists())

    report = {}
    prune_run(context(src, archive, manifest, Hooks(**{stage: create})), [src], apply=True,
              codex_probed=False, report=report)
    assert outcomes(report) == {f"-p/{OLD}": "pruned"}  # current
    assert resolved == [stage == "after_precheck"]  # dangling from creation once quarantined
    assert link.is_symlink() and not link.exists()
