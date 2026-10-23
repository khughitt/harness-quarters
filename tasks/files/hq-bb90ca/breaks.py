"""Break-check each SL11 assertion in a scratch copy: one targeted change per test must fail it."""
import json, shutil, subprocess, sys, os
from pathlib import Path
SRC = Path(sys.argv[1]); SCR = Path(sys.argv[2])
CM = "turns/.claude/projects/-w-gamma/c0000000-0000-4000-8000-000000000021.jsonl"
CT3 = "turns/.claude/projects/-w-gamma/c0000000-0000-4000-8000-000000000024.jsonl"
XE = "turns/.codex/sessions/2026/10/12/rollout-2026-10-12T10-00-00-01900000-0000-7000-8000-0000000000e1.jsonl"

def rw(path, fn):
    lines = path.read_text().splitlines(keepends=True)
    path.write_text("".join(fn(lines)))

def move_feedback(ls):  # CM:24 (feedback) after CM:26 (summary)
    ls = list(ls); fb = ls.pop(23); ls.insert(25, fb); return ls

def drop_skill_id(ls):
    out = []
    for l in ls:
        r = json.loads(l)
        if r.get("sourceToolUseID"): r["sourceToolUseID"] = "toolu_fx_other"
        out.append(json.dumps(r, separators=(",", ":")) + "\n")
    return out

def queued_not_human(ls):
    return [l.replace('"origin":{"kind":"human"},"timestamp"', '"origin":{"kind":"task-notification"},"timestamp"') for l in ls]

def drop_abort(ls):
    return [l for l in ls if '"turn_aborted"' not in l]

def swap_author(ls):
    return [l.replace('"author":"/root/worker","recipient":"/root"', '"author":"/root","recipient":"/root/worker"') for l in ls]

def chain_ok(ls):
    return [l.replace('"is_error":true', '"is_error":false', 1) if "toolu_fx_v2" in l and "tool_result" in l else l for l in ls]

BREAKS = [
    ("test_sl11_marker_session_turn_ends_and_markers", lambda f: rw(f / CM, move_feedback)),
    ("test_sl11_skill_load_record_shares_the_turn_prompt", lambda f: rw(f / CM, drop_skill_id)),
    ("test_sl11_local_commands_and_queued_human_attachment", lambda f: rw(f / CM, queued_not_human)),
    ("test_sl11_codex_statuses_by_closing_event", lambda f: rw(f / XE, drop_abort)),
    ("test_sl11_agent_message_direction", lambda f: rw(f / XE, swap_author)),
    ("test_sl11_fork_without_parent_holds_only_copied_history",
     lambda f: shutil.copy(f / XE, f / "turns/.codex/sessions/2026/10/12/rollout-2026-10-12T08-00-00-01900000-0000-7000-8000-0000000000f9.jsonl")),
    ("test_sl11_task_document_and_evidence_sessions", lambda f: rw(f / CT3, chain_ok)),
    ("test_sl11_escaped_needle_is_absent_from_the_bytes",
     lambda f: (f / "captures/escaped.jsonl").write_text((f / "captures/escaped.jsonl").read_text().replace("\\u006eeedle", "needle"))),
]

XK = "turns/.codex/sessions/2026/10/12/rollout-2026-10-12T11-00-00-01900000-0000-7000-8000-0000000000f2.jsonl"
TD = "captures/tasks-show-zz-000021.json"

def edit_line(n, fn):
    def go(ls):
        ls = list(ls); r = json.loads(ls[n - 1]); fn(r); ls[n - 1] = json.dumps(r, separators=(",", ":")) + "\n"; return ls
    return go

def set_path(r, path, value):
    for k in path[:-1]: r = r[k]
    r[path[-1]] = value

BREAKS += [
    ("test_sl11_skill_load_record_shares_the_turn_prompt", lambda f: rw(f / CM, edit_line(35, lambda r: set_path(r, ["promptId"], "p-other")))),
    ("test_sl11_claude_triggers_markers_and_synthetic_end", lambda f: rw(f / CM, edit_line(44, lambda r: set_path(r, ["origin", "kind"], "human")))),
    ("test_sl11_claude_triggers_markers_and_synthetic_end", lambda f: rw(f / CM, edit_line(58, lambda r: set_path(r, ["message", "model"], "claude-model-a")))),
    ("test_sl11_claude_triggers_markers_and_synthetic_end", lambda f: rw(f / CM, edit_line(52, lambda r: set_path(r, ["message", "content"], [{"type": "text", "text": "keep going"}])))),
    ("test_sl11_codex_finals_questions_and_phases", lambda f: rw(f / XE, edit_line(14, lambda r: r["payload"]["item"].pop("questions")))),
    ("test_sl11_codex_finals_questions_and_phases", lambda f: rw(f / XE, edit_line(26, lambda r: set_path(r, ["payload", "last_agent_message"], "done")))),
    ("test_sl11_fork_without_parent_holds_only_copied_history", lambda f: rw(f / XK, edit_line(1, lambda r: set_path(r, ["payload", "subagent_history_start_ordinal"], 2)))),
    ("test_sl11_fork_without_parent_holds_only_copied_history", lambda f: rw(f / XK, edit_line(6, lambda r: set_path(r, ["payload", "phase"], "commentary")))),
    ("test_sl11_task_document_and_evidence_sessions", lambda f: (f / TD).write_text((f / TD).read_text().replace('"at": "2026-10-12T12:00:30Z"', '"at": "2026-10-12T12:05:00Z"'))),
    ("test_sl11_escaped_needle_is_absent_from_the_bytes", lambda f: (f / "captures/escaped-malformed.jsonl").write_text((f / "captures/escaped-malformed.jsonl").read_text().rstrip("\n") + "}}\n")),
]

def swap_17_18(ls):
    ls = list(ls); ls[16], ls[17] = ls[17], ls[16]; return ls

def one_based(ls):
    out = []
    for l in ls:
        r = json.loads(l); r["ordinal"] += 1; out.append(json.dumps(r, separators=(",", ":")) + "\n")
    return out

BREAKS += [
    ("test_sl11_local_commands_and_queued_human_attachment", lambda f: rw(f / CM, swap_17_18)),
    ("test_sl11_codex_statuses_by_closing_event", lambda f: rw(f / XK, one_based)),
]

env = {"PATH": os.environ["PATH"], "HOME": str(SCR / "home"), "XDG_CACHE_HOME": os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))}
def run(root, test):
    return subprocess.run(["uv", "run", "-q", "--with", "pytest", "pytest", "-q", "-p", "no:cacheprovider",
                           f"tools/test_session_log_cases.py::{test}"], cwd=root, env=env,
                          capture_output=True, text=True).returncode

ok = True
for test, brk in BREAKS:
    root = SCR / "copy"
    shutil.rmtree(root, ignore_errors=True)
    (root / "docs").mkdir(parents=True)
    shutil.copytree(SRC / "tools/fixtures", root / "tools/fixtures")
    shutil.copy(SRC / "tools/test_session_log_cases.py", root / "tools/")
    shutil.copytree(SRC / "docs/notes", root / "docs/notes")
    clean = run(root, test)
    brk(root / "tools/fixtures/session-logs")
    broken = run(root, test)
    shutil.rmtree(root / "tools/fixtures"); shutil.copytree(SRC / "tools/fixtures", root / "tools/fixtures")
    restored = run(root, test)
    verdict = clean == 0 and broken != 0 and restored == 0
    ok &= verdict
    print(f"{'ok  ' if verdict else 'FAIL'} {test}: clean={clean} broken={broken} reverted={restored}")
sys.exit(0 if ok else 1)
