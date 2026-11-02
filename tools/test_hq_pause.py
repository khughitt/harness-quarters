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
LINE = "active 1:12/16:00 calls 140/500 spawns 3/30 compactions 0/2 paused:no budget:none notify:ok"


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
    with store(home).locked(harness, root) as st:
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
    assert result.stdout.strip() == LINE.replace("compactions 0/2", "compactions -/2 (count your own)")


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
    with store(home).locked("claude-code", "s1") as st:
        st.cwd = "/x"
    result = hq(home, "status", "--session", "s1")
    assert result.returncode == 1 and result.stdout == ""
    assert "no turn" in result.stderr


def test_limits_text_and_json(home):
    text = hq(home, "limits")
    assert text.returncode == 0, text.stderr
    assert text.stdout.strip() == "active 16:00 calls 500 spawns 30 compactions 2"
    data = json.loads(hq(home, "limits", "--json").stdout)
    assert data == {"active_seconds": 57600, "calls": 500, "spawns": 30, "compactions": 2}
