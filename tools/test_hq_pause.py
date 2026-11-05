"""`hq pause status` and `hq pause limits` over synthetic state under a temp XDG_STATE_HOME."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from turn_pause import limits as limits_mod
from turn_pause.counters import TurnState
from turn_pause.state import Store, state_path

TOOL = Path(__file__).resolve().parent / "hq"
LINE = "active 1h12m/16h00m root calls 140/500 tree spawns 3/60 root compactions 0/2 (advisory) paused:no budget:none notify:ok"


@pytest.fixture
def home(tmp_path):
    (tmp_path / "home").mkdir()
    (tmp_path / "state").mkdir()
    return tmp_path


def store(home):
    return Store(state_path({"XDG_STATE_HOME": str(home / "state")}))


def seed(home, harness, root, cwd="/work/a", workers=(), calls=140, **fields):
    defaults, _ = limits_mod.load()
    turn = TurnState(started=1.0, limits=defaults, limits_sha="x", active=4320.0, calls=calls, spawns=3)
    with store(home).locked(harness, root) as record:
        st = record.state
        st.turn, st.cwd, st.workers = turn, cwd, set(workers)
        st.notified = True
        for key, value in fields.items():
            setattr(st, key, value)


def hq(home, *args, thread=None, cwd=None):
    env = {"PATH": os.environ["PATH"], "HOME": str(home / "home"), "XDG_STATE_HOME": str(home / "state")}
    if thread:
        env["CODEX_THREAD_ID"] = thread
    return subprocess.run([sys.executable, str(TOOL), "pause", *args], env=env, cwd=cwd or str(home),
                          capture_output=True, text=True)


def test_status_for_codex_root(home):
    seed(home, "codex", "r1")
    result = hq(home, "status", thread="r1")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == LINE.replace("compactions 0/2 (advisory)", "compactions -/2 (advisory, unhooked)")


def test_status_for_worker_prints_its_roots_counts(home):
    seed(home, "codex", "r1", workers=["w9"])
    result = hq(home, "status", thread="w9", cwd=str(home))
    assert result.returncode == 0, result.stderr
    assert "calls 140/500" in result.stdout


def test_status_by_cwd_claude(home):
    seed(home, "claude-code", "s1", cwd=str(home))
    result = hq(home, "status")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == LINE


def test_status_cwd_picks_newest(home):
    seed(home, "claude-code", "old", cwd=str(home))
    os.utime(store(home)._path("claude-code-old.json"), (1, 1))
    seed(home, "claude-code", "new", cwd=str(home), paused="calls")
    assert "paused:calls" in hq(home, "status").stdout


def test_status_session_flag(home):
    seed(home, "claude-code", "s1")
    result = hq(home, "status", "--session", "s1")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == LINE


def test_status_session_flag_beats_thread_env(home):
    seed(home, "claude-code", "s1")
    seed(home, "codex", "r1", calls=0)
    assert hq(home, "status", "--session", "s1", thread="r1").stdout.strip() == LINE


def test_status_paused_budget_and_notify_error(home):
    seed(home, "claude-code", "s1", paused="spawns", budget_note="2h", notified=False,
         notify_error="boom\nbad")
    out = hq(home, "status", "--session", "s1").stdout.strip()
    assert out.endswith("paused:spawns budget:2h notify:error: boom bad")


def test_status_json(home):
    seed(home, "claude-code", "s1")
    data = json.loads(hq(home, "status", "--session", "s1", "--json").stdout)
    assert data["harness"] == "claude-code" and data["root"] == "s1"
    assert data["active"] == {"used": 4320.0, "limit": 57600}
    assert data["calls"] == {"used": 140, "limit": 500}
    assert data["compactions"] == {"used": 0, "limit": 2}
    assert data["paused"] is None and data["notify"] == "ok"


def test_status_json_codex_compactions_null(home):
    seed(home, "codex", "r1")
    data = json.loads(hq(home, "status", "--json", thread="r1").stdout)
    assert data["compactions"] == {"used": None, "limit": 2}


def test_status_no_state_is_an_error(home):
    result = hq(home, "status", thread="nope")
    assert result.returncode == 1 and result.stdout == ""
    assert "no pause state" in result.stderr and "nope" in result.stderr


def test_status_no_state_by_cwd_names_cwd(home):
    result = hq(home, "status")
    assert result.returncode == 1 and result.stdout == ""
    assert str(home) in result.stderr


def test_status_state_without_turn_is_an_error(home):
    with store(home).locked("claude-code", "s1") as record:
        st = record.state
        st.cwd = "/x"
    result = hq(home, "status", "--session", "s1")
    assert result.returncode == 1 and result.stdout == ""
    assert "no turn" in result.stderr


def test_limits_text_and_json(home):
    text = hq(home, "limits")
    assert text.returncode == 0, text.stderr
    assert text.stdout.strip() == "active 16h00m root calls 500 tree spawns 60 root compactions 2 (advisory)"
    data = json.loads(hq(home, "limits", "--json").stdout)
    assert data == {"active_seconds": 57600, "calls": 500, "spawns": 60, "compactions": 2}


def snapshot_tree(root: Path) -> dict[str, tuple[bytes, int, int]]:
    if not root.exists():
        return {}
    out = {}
    for path in sorted(root.rglob("*")):
        st = path.stat()
        out[str(path.relative_to(root))] = (path.read_bytes() if path.is_file() else b"<dir>", st.st_mtime_ns, st.st_mode & 0o777)
    return out


def test_history_and_list_unavailable_coverage_and_readonly_when_store_missing(home):
    state_root = Path(state_path({"XDG_STATE_HOME": str(home / "state")}))
    assert not state_root.exists()
    before = snapshot_tree(home / "state")
    for subcmd, key in (("history", "events"), ("list", "summaries")):
        res = hq(home, subcmd, "--json")
        assert res.returncode == 0, res.stderr
        data = json.loads(res.stdout)
        assert data["version"] == 1
        assert data["coverage"]["status"] == "unavailable"
        assert data[key] == []
        assert data["truncated"] is False
        assert data["cleanup_debt"] == 0
        assert data["diagnostics"]
        text_res = hq(home, subcmd)
        assert text_res.returncode == 0, text_res.stderr
        assert "coverage:unavailable" in text_res.stdout
    after = snapshot_tree(home / "state")
    assert before == after and not state_root.exists()


def test_history_and_list_readonly_filters_ordering_and_codex_compactions(home):
    from turn_pause import history as hist_mod
    st = store(home)
    defaults, _ = limits_mod.load()
    with st.locked("codex", "r1") as rec:
        rec.created_at = 1793600000.0
        rec.state.cwd = str(home)
        rec.state.turn = TurnState(started=1793600010.0, limits=defaults, limits_sha="sha1",
                                   active=120.0, calls=375, spawns=2, compactions=0)
        hist_mod.start_turn(rec, 1793600010.0, origin="genuine_user", before=None,
                            after=hist_mod.snapshot(rec.state, compactions_counted=False))
        hist_mod.append_event(rec, "warning", 1793600100.0, reason="calls",
                              snapshot=hist_mod.snapshot(rec.state, compactions_counted=False))
        prev = hist_mod.snapshot(rec.state, compactions_counted=False)
        rec.state.turn = TurnState(started=1793600200.0, limits=defaults, limits_sha="sha1",
                                   active=30.0, calls=10, spawns=0, compactions=0)
        hist_mod.start_turn(rec, 1793600200.0, origin="genuine_user", before=prev,
                            after=hist_mod.snapshot(rec.state, compactions_counted=False))
    with st.locked("claude-code", "c1") as rec:
        rec.created_at = 1793600050.0
        rec.state.cwd = "/work/other"
        rec.state.paused = "spawns"
        rec.state.turn = TurnState(started=1793600060.0, limits=defaults, limits_sha="sha2",
                                   active=600.0, calls=50, spawns=61, compactions=1)
        hist_mod.start_turn(rec, 1793600060.0, origin="genuine_user", before=None,
                            after=hist_mod.snapshot(rec.state, compactions_counted=True))
        hist_mod.append_event(rec, "enforced_pause", 1793600150.0, reason="spawns",
                              snapshot=hist_mod.snapshot(rec.state, compactions_counted=True),
                              notification=dict(outcome="pending", error_code=None, desktop="unknown",
                                                relay="unknown", receipt="unknown", pause_sequence=2))
    assert st.end("claude-code", "c1", 1793600300.0, compactions_counted=True)

    state_root = Path(state_path({"XDG_STATE_HOME": str(home / "state")}))
    for p in state_root.glob("*.json"):
        os.utime(p, (1793600300, 1793600300))
    before = snapshot_tree(home / "state")

    # Ambient thread and cwd must not narrow history or list without --session
    res = hq(home, "history", "--json", thread="r1", cwd=str(home))
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["version"] == 1
    assert data["coverage"]["status"] == "available"
    assert data["coverage"]["observation"] == "per_root_atomic"
    assert {e["root"] for e in data["events"]} == {"r1", "c1"}
    # Deterministic newest-first ordering, including same-timestamp turn_reset and turn_start at 1793600200.0
    keys = [(e["at"], e["harness"], e["root"], e["generation"], e["turn"], e["sequence"]) for e in data["events"]]
    assert keys == sorted(keys, reverse=True)
    reset_pair = [e for e in data["events"] if e["root"] == "r1" and e["at"] == 1793600200.0]
    assert [e["kind"] for e in reset_pair] == ["turn_start", "turn_reset"]
    codex_ev = next(e for e in data["events"] if e["harness"] == "codex")
    claude_ev = next(e for e in data["events"] if e["harness"] == "claude-code")
    assert codex_ev["snapshot"]["compactions"]["used"] is None
    assert claude_ev["snapshot"]["compactions"]["used"] == 1

    # Window [since, until): since is inclusive, until is exclusive
    from datetime import datetime, timezone
    since_iso = datetime.fromtimestamp(1793600100.0, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    until_iso = datetime.fromtimestamp(1793600200.0, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    w_res = hq(home, "history", "--since", since_iso, "--until", until_iso, "--json")
    assert w_res.returncode == 0, w_res.stderr
    w_events = json.loads(w_res.stdout)["events"]
    assert [e["at"] for e in w_events] == [1793600150.0, 1793600100.0]

    # Limit -n truncates and sets truncated=True
    lim_res = hq(home, "history", "-n", "2", "--json")
    lim_data = json.loads(lim_res.stdout)
    assert len(lim_data["events"]) == 2 and lim_data["truncated"] is True

    # Summaries via hq pause list
    list_res = hq(home, "list", "--json", thread="r1", cwd=str(home))
    assert list_res.returncode == 0, list_res.stderr
    list_data = json.loads(list_res.stdout)
    assert len(list_data["summaries"]) == 3
    assert [(s["root"], s["turn"]) for s in list_data["summaries"]] == [("c1", 1), ("r1", 2), ("r1", 1)]
    c1_sum = list_data["summaries"][0]
    assert c1_sum["started_at"] == 1793600060.0 and c1_sum["ended_at"] == 1793600300.0
    assert c1_sum["enforced_pause"] == "spawns" and c1_sum["root_active"] is False
    r1_t2 = list_data["summaries"][1]
    assert r1_t2["started_at"] == 1793600200.0 and r1_t2["ended_at"] is None and r1_t2["root_active"] is True

    # Filter by --session and --harness
    s_res = hq(home, "list", "--session", "c1", "--harness", "claude-code", "--json")
    assert [s["root"] for s in json.loads(s_res.stdout)["summaries"]] == ["c1"]

    # Text mode names count scopes, reason, and coverage
    txt = hq(home, "history").stdout
    assert "coverage:available" in txt and "root_attempts" in txt and "spawns" in txt
    ltxt = hq(home, "list").stdout
    assert "coverage:available" in ltxt and "spawns" in ltxt

    after = snapshot_tree(home / "state")
    assert before == after


def test_history_and_list_reject_invalid_limits_dates_and_corrupt_records(home):
    seed(home, "codex", "r1")
    for bad_args in (
        ("history", "-n", "0"),
        ("history", "-n", "1001"),
        ("list", "-n", "-1"),
        ("history", "--since", "2026-11-04T00:00:00"),
        ("history", "--until", "2026-11-04"),
        ("list", "--since", "not-a-timestamp"),
        ("history", "--since", "2026-11-04T02:00:00Z", "--until", "2026-11-04T01:00:00Z"),
        ("history", "--since", "2026-11-04T02:00:00Z", "--until", "2026-11-04T02:00:00Z"),
        ("history", "--session", "../bad"),
    ):
        res = hq(home, *bad_args)
        assert res.returncode == 1 and res.stdout == "" and res.stderr

    # Corrupt record fails with exit 1 without mutating store
    bad_path = Path(state_path({"XDG_STATE_HOME": str(home / "state")})) / "codex-r1.json"
    bad_path.write_text("{corrupt")
    before = snapshot_tree(home / "state")
    assert hq(home, "history", "--json").returncode == 1
    assert hq(home, "list", "--json").returncode == 1
    assert snapshot_tree(home / "state") == before


def test_history_and_list_truncation_cleanup_debt_and_partial_coverage(home, monkeypatch):
    from turn_pause import history as hist_mod
    st = store(home)
    defaults, _ = limits_mod.load()
    with st.locked("codex", "truncated") as rec:
        rec.created_at = 100.0
        rec.state.turn = TurnState(started=100.0, limits=defaults, limits_sha="sha", active=1.0, calls=1, spawns=0)
        hist_mod.start_turn(rec, 100.0, origin="genuine_user", before=None,
                            after=hist_mod.snapshot(rec.state, compactions_counted=False))
        for i in range(130):
            hist_mod.append_event(rec, "warning", 101.0 + i, reason="calls",
                                  snapshot=hist_mod.snapshot(rec.state, compactions_counted=False))
    # Imported/uninitialized root with no turn
    with st.locked("codex", "unobserved") as rec:
        rec.created_at = 50.0
    # Expired ended root contributing to cleanup_debt
    with st.locked("claude-code", "expired") as rec:
        rec.created_at = 10.0
        rec.state.turn = TurnState(started=10.0, limits=defaults, limits_sha="sha", active=1.0, calls=1, spawns=0)
        hist_mod.start_turn(rec, 10.0, origin="genuine_user", before=None,
                            after=hist_mod.snapshot(rec.state, compactions_counted=True))
    assert st.end("claude-code", "expired", 20.0, compactions_counted=True)

    before = snapshot_tree(home / "state")
    h_data = json.loads(hq(home, "history", "--json").stdout)
    l_data = json.loads(hq(home, "list", "--json").stdout)
    assert snapshot_tree(home / "state") == before

    assert h_data["coverage"]["status"] == "partial"
    assert h_data["truncated"] is True
    assert h_data["cleanup_debt"] >= 1
    assert h_data["retention"]["ended_seconds"] == 30 * 86400
    assert h_data["retention"]["max_ended"] == 512
    assert h_data["retention"]["max_events_per_root"] == 128
    assert h_data["retention"]["max_bytes_per_root"] == 131072
    assert h_data["retention"]["dropped_count"] == 3
    assert any("unobserved" in d for d in h_data["diagnostics"])
    assert any("dropped" in d for d in h_data["diagnostics"])

    # Unobserved root must not acquire a fabricated turn summary, and truncated turn has started_at=None
    assert {s["root"] for s in l_data["summaries"]} == {"truncated", "expired"}
    trunc_sum = next(s for s in l_data["summaries"] if s["root"] == "truncated")
    assert trunc_sum["started_at"] is None and trunc_sum["truncated"] is True

    # Disappearing catalog entry is reported as partial coverage diagnostic
    from hq_cli import pause as pause_cli
    real_load = Store._load

    def vanishing_load(self, path, **kw):
        if path.endswith("codex-unobserved.json"):
            return None
        return real_load(self, path, **kw)

    monkeypatch.setattr(Store, "_load", vanishing_load)
    args = type("A", (), {"session": None, "harness": None, "since": None, "until": None, "limit": 50, "json": True})()
    vanished = json.loads(pause_cli.history(args, {"XDG_STATE_HOME": str(home / "state")}))
    assert vanished["coverage"]["status"] == "partial"
    assert vanished["coverage"]["disappeared_files"] == 1
    assert any("disappeared" in d for d in vanished["diagnostics"])


def test_history_and_list_do_not_publish_prompt_guards(home):
    from turn_pause import history as hist_mod
    from turn_pause.state import Wakeup
    st = store(home)
    defaults, _ = limits_mod.load()
    sentinel = "RAW_SCHEDULE_SENTINEL_99"
    digest = "d" * 64
    with st.locked("claude-code", "guarded") as rec:
        rec.state.cwd = "/private/cwd/sentinel"
        rec.state.notify_error = "private_notify_sentinel"
        rec.state.budget_note = "private_budget_sentinel"
        rec.state.cron_jobs = {"job1": sentinel}
        rec.state.wakeups = [Wakeup(sentinel, 100.0, 200.0)]
        rec.state.turn = TurnState(started=10.0, limits=defaults, limits_sha="sha", active=5.0, calls=10, spawns=1)
        hist_mod.start_turn(rec, 10.0, origin="genuine_user", before=None,
                            after=hist_mod.snapshot(rec.state, compactions_counted=True))
    assert st.end("claude-code", "guarded", 20.0, compactions_counted=True)
    with st.locked("claude-code", "guarded", create=False) as rec:
        rec.prompt_guards = {"cron": [digest], "wakeups": [[digest, 100.0, 200.0]]}

    for subcmd in ("history", "list"):
        for extra in ((), ("--json",)):
            res = hq(home, subcmd, *extra)
            assert res.returncode == 0, res.stderr
            out = res.stdout
            for forbidden in (sentinel, digest, "prompt_guards", "/private/cwd/sentinel",
                              "private_notify_sentinel", "private_budget_sentinel"):
                assert forbidden not in out
            if extra:
                parsed = json.loads(out)
                rows = parsed.get("events") or parsed.get("summaries")
                for row in rows:
                    snap = row.get("snapshot")
                    if snap is not None:
                        assert set(snap) == set(hist_mod.SNAP_FIELDS)

    fixture_path = Path(__file__).resolve().parent / "fixtures/turn-pause/history/obs-handoff-cases.json"
    assert fixture_path.is_file()
    raw_fixture = fixture_path.read_text()
    assert "prompt_guards" not in raw_fixture and sentinel not in raw_fixture
    bundle = json.loads(raw_fixture)
    case_ids = {c["id"] for c in bundle["cases"]}
    assert {"A", "B", "C", "D", "E", "F", "G",
            "control_warning_continued", "control_ordinary_gate",
            "control_genuine_resume", "control_missing_conflicting"} <= case_ids
    for case in bundle["cases"]:
        assert isinstance(case["hook_events"], list)
        assert isinstance(case["task_evidence"], list)
        assert isinstance(case["session_evidence"], list)
        for ev in case["hook_events"]:
            hist_mod.validate_event(ev)
            assert "prompt_guards" not in ev and "cwd" not in ev

    # Verify faithful CLI presentation of the fixture's hook events
    fix_home = home / "fix_home"
    (fix_home / "home").mkdir(parents=True)
    (fix_home / "state").mkdir(parents=True)
    fix_store = store(fix_home)
    by_root = {}
    for case in bundle["cases"]:
        key = (case["harness"], case["root"])
        entry = by_root.setdefault(key, {
            "generation": case["generation"],
            "created_at": case["created_at"],
            "ended_at": case["ended_at"],
            "events": [],
        })
        entry["events"].extend(case["hook_events"])
    for (h_name, r_name), meta in by_root.items():
        with fix_store.locked(h_name, r_name) as rec:
            rec.generation = meta["generation"]
            rec.created_at = meta["created_at"]
            rec.ended_at = meta["ended_at"]
            if meta["ended_at"] is not None:
                rec.state = None
            rec.events = sorted(meta["events"], key=lambda e: e["sequence"])
            rec.turn_serial = max(e["turn"] for e in rec.events)
            rec.event_serial = max(e["sequence"] for e in rec.events)
    fix_hist = json.loads(hq(fix_home, "history", "-n", "100", "--json").stdout)
    fix_list = json.loads(hq(fix_home, "list", "-n", "100", "--json").stdout)
    assert fix_hist["coverage"]["status"] == "available"
    assert len(fix_hist["events"]) == sum(len(c["hook_events"]) for c in bundle["cases"])
    by_turn = {(s["harness"], s["root"], s["turn"]): s for s in fix_list["summaries"]}
    assert by_turn[("claude-code", "f5ed2d6a-dc73-443e-ac25-c0a4357da4cb", 1)]["enforced_pause"] == "spawns"
    assert by_turn[("codex", "01a19f20-a422-75b0-8476-0ed9ba0dd8c9", 1)]["enforced_pause"] is None
    assert by_turn[("codex", "01a1a10b-15de-7a00-81ba-4469c83141b8", 1)]["end_kind"] == "turn_reset"
    assert by_turn[("claude-code", "99999999-3333-4333-8333-333333333333", 1)]["end_kind"] == "turn_resume"
