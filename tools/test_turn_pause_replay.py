"""The turn-pause replay: stored session trees through the hook's own engine.feed
(spec: Measured range, The unit, Counters, Limits, Verification).

Fixtures under tools/fixtures/turn-pause/replay/: a Claude Code tree (root plus one
subagent) and a Codex tree (root plus three worker rollouts), each with the hook payload
sequence it would have produced (hook/payloads.json). Times are offsets from T,
2026-10-10T12:00:00Z. No test reads a live store."""
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from turn_pause import hook, replay
from turn_pause.limits import DEFAULTS_PATH, load
from turn_pause.state import Store, state_dir

TOOLS = Path(__file__).parent
FIX = TOOLS / 'fixtures' / 'turn-pause' / 'replay'
T = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc).timestamp()

CLAUDE_ID = '5d1e7a52-0c3b-4f7e-9a61-2b8c4d0e9f13'
CLAUDE_PROJECTS = FIX / 'claude' / 'projects'
CLAUDE_ROOT = CLAUDE_PROJECTS / '-tmp-replay' / f'{CLAUDE_ID}.jsonl'
CLAUDE_SUB = CLAUDE_PROJECTS / '-tmp-replay' / CLAUDE_ID / 'subagents' / 'agent-a1b2c3d4e5f6a7b8c.jsonl'
CODEX_ID = '01a18943-2b9d-7e50-926f-b74169571349'
KIDS = ['01a18944-0001-7000-8000-000000000001', '01a18944-0002-7000-8000-000000000002',
        '01a18944-0003-7000-8000-000000000003']
CODEX_SESSIONS = FIX / 'codex' / 'sessions'
CODEX_DAY = CODEX_SESSIONS / '2026' / '10' / '10'
CODEX_ROOT = CODEX_DAY / f'rollout-2026-10-10T08-00-00-{CODEX_ID}.jsonl'
CODEX_KIDS = [CODEX_DAY / f'rollout-2026-10-10T08-00-{10 + 2 * k:02d}-{kid}.jsonl' for k, kid in enumerate(KIDS)]


def write_limits(path, **over):
    values = dict(active_seconds=14400, calls=500, spawns=30, compactions=2)
    values.update(over)
    path.write_text(''.join(f'{k} = {v}\n' for k, v in values.items()))
    return path


def tree(harness, kids=None):
    if harness == 'claude-code':
        return replay.read_claude_tree(CLAUDE_ROOT, [CLAUDE_SUB] if kids is None else kids)
    return replay.read_codex_tree(CODEX_ROOT, CODEX_KIDS if kids is None else kids, replay.codex_unhooked())


def run(harness, limits_path=DEFAULTS_PATH, kids=None, t1=None):
    root, steps = tree(harness, kids)
    limits, sha = load(limits_path)
    return replay.replay(harness, root, steps, limits, sha, t1=t1)


def counts(turn):
    s = turn.state
    return s.active, s.calls, s.spawns, s.compactions


# --- Claude Code ----------------------------------------------------------------------

def test_claude_turns_start_only_at_genuine_prompts():
    """A task notification, an interrupt marker and a scheduled wake start no turn."""
    turns = run('claude-code')
    assert [t.start - T for t in turns] == [0.0, 9100.0, 20000.0]
    assert all(t.root == CLAUDE_ID for t in turns)


def test_claude_counts_root_calls_tree_spawns_and_root_compactions():
    """Root calls only (the subagent's Read is not one), one Agent spawn, one compaction."""
    one, two, _ = run('claude-code')
    assert counts(one)[1:] == (4, 1, 1)
    assert counts(two)[1:] == (2, 0, 0)


def test_claude_active_time_follows_calls_in_flight_and_the_idle_gap():
    """Turn 1: 1500 s of `just test` in flight counts in full; the 2 h AskUserQuestion wait
    counts nothing; the 87 s gap before the task notification counts (under 10 minutes).
    Turn 2: the 1199 s quiet gap before the scheduled wake counts nothing."""
    one, two, three = run('claude-code')
    assert one.state.active == pytest.approx(2 + 1 + 1 + 0.5 + 0.5 + 1 + 1 + 1 + 1 + 1500 + 1.5 + 1.5 + 0 + 1 + 87 + 1)
    assert two.state.active == pytest.approx(2 + 1 + 1 + 0 + 2 + 1 + 1)
    assert three.state.active == pytest.approx(2 + 3 + 0 + 1)


def test_claude_call_refused_by_another_hook_closes_at_the_next_user_wait():
    """Turn 3: a Bash a relay hook refused gets no PostToolUse, so it stays open until
    the AskUserQuestion starts; the 5 h wait after it is not active time."""
    _, steps = tree('claude-code')
    refused = [s for s in steps if any(e.kind == 'tool_end' and e.call_id == 'toolu_07'
                                       for e in s.events)]
    assert refused == []
    cut = run('claude-code', t1=T + 20004.0)[2]
    assert cut.state.in_flight == {'toolu_07': None}
    cut = run('claude-code', t1=T + 20006.0)[2]
    assert cut.state.in_flight == {}


# --- Codex ----------------------------------------------------------------------------

def test_codex_exec_with_three_nested_calls_is_three_root_calls():
    """The outer exec is never a call; each nested call is, from its recorded start."""
    _, steps = tree('codex')
    starts = [(round(e.t - T, 3), e.call_id) for s in steps for e in s.events
              if e.kind == 'tool_start' and e.agent is None]
    assert starts[:3] == [(5.1, 'exec-r1'), (5.4, 'exec-r2'), (5.7, 'exec-r3')]
    assert not any(e.call_id and e.call_id.startswith('call_e') for s in steps for e in s.events)
    one, two = run('codex')
    # 3 nested + 3 spawn_agent + 1 wait_agent + make long + git status; the workers' own calls are not root calls
    assert one.state.calls == 9
    assert two.state.calls == 1


def test_codex_spawns_count_started_workers_from_child_rollouts():
    one, _ = run('codex')
    assert one.state.spawns == 3
    one, _ = run('codex', kids=CODEX_KIDS[:2])
    assert one.state.spawns == 2
    assert one.state.calls == 9  # the third spawn_agent call is still a call


def test_codex_no_compaction_is_counted():
    assert [t.state.compactions for t in run('codex')] == [0, 0]


def test_codex_yielded_exec_command_stays_in_flight_across_an_unhooked_wait():
    """`make long` yields inside a yielded cell and ends on its own at 1000 s, while the
    model sits in the unhooked `wait`: no PostToolUse ever comes, so it stays in flight
    until the agent's Stop and the 700 s quiet gap after it ends counts in full.
    `npm run build` yields too, but a write_stdin poll ends it: it closes at 2030 s."""
    one, two = run('codex')
    assert one.state.active == pytest.approx(1705.0 - 1.0)
    assert two.state.active == pytest.approx(35.0)
    cut = run('codex', t1=T + 1699.0)[0]
    assert cut.state.in_flight == {'exec-y1': None}
    cut = run('codex', t1=T + 2032.0)[1]
    assert cut.state.in_flight == {}


# --- the pause point ------------------------------------------------------------------

@pytest.mark.parametrize('harness, over, expected', [
    ('claude-code', dict(calls=2), (9.0, 'calls', 'toolu_03', None)),
    ('codex', dict(calls=2), (5.7, 'calls', 'exec-r3', None)),
    ('codex', dict(spawns=2), (15.3, 'spawns', 'exec-c3', KIDS[2])),
    ('codex', dict(active_seconds=600), (1700.1, 'active', 'exec-b1', None)),
])
def test_first_pause_point_is_the_first_call_after_a_limit_is_crossed(tmp_path, harness, over, expected):
    turns = run(harness, write_limits(tmp_path / 'limits.toml', **over))
    pause = turns[0].pause
    assert (round(pause.t - T, 3), pause.limit, pause.call_id, pause.agent) == expected
    assert turns[1].pause is None


def test_default_limits_pause_neither_fixture():
    assert [t.pause for h in ('claude-code', 'codex') for t in run(h)] == [None] * 5


# --- the hook path --------------------------------------------------------------------

def hook_path(harness, limits_path, tmp_path, monkeypatch):
    """The fixture's hook payloads through the hook itself (hook.decide with a real Store).
    Returns each turn's last state and the first refused call (call id, limit, t)."""
    monkeypatch.setattr(hook.notify, 'send', lambda *a, **k: None)
    env = {'PATH': '/usr/bin:/bin', 'HOME': str(tmp_path / 'home'), 'XDG_STATE_HOME': str(tmp_path / 'state'),
           'XDG_RUNTIME_DIR': str(tmp_path / 'run')}
    store = Store(state_dir(env))
    records = json.loads((FIX / ('claude' if harness == 'claude-code' else 'codex') / 'hook' / 'payloads.json')
                         .read_text())['records']
    turns, pause = [], None
    for r in records:
        payload = r['payload']
        out = hook.decide(harness, r['event'], payload, r['t'], store, limits_path, env)
        st = store.read(harness, payload['session_id'])
        refused = out is not None and out['hookSpecificOutput'].get('permissionDecision') == 'deny'
        if refused and pause is None:
            pause = (payload['tool_use_id'], st.paused, r['t'])
        if turns and turns[-1].started == st.turn.started:
            turns[-1] = st.turn
        else:
            turns.append(st.turn)
    return turns, pause


@pytest.mark.parametrize('harness, over', [
    ('claude-code', dict(calls=2)),
    ('codex', dict(calls=2)),
    ('codex', dict(spawns=2)),
    ('codex', dict(active_seconds=600)),
])
def test_replay_matches_hook_path(tmp_path, monkeypatch, harness, over):
    """Same tree, two ways: the hook payloads through the hook, and the transcript through
    the replay converter. Equal counters per turn (active within 1 s), the same pause."""
    defaults = write_limits(tmp_path / 'defaults.toml')
    hooked, _ = hook_path(harness, defaults, tmp_path / 'a', monkeypatch)
    replayed = run(harness, defaults)
    assert len(hooked) == len(replayed) == (3 if harness == 'claude-code' else 2)
    for h, r in zip(hooked, replayed):
        assert abs(h.started - r.start) <= 1.0
        assert abs(h.active - r.state.active) <= 1.0
        assert (h.calls, h.spawns, h.compactions) == counts(r)[1:]
    low = write_limits(tmp_path / 'low.toml', **over)
    _, (call, limit, t) = hook_path(harness, low, tmp_path / 'b', monkeypatch)
    pause = run(harness, low)[0].pause
    assert (pause.call_id, pause.limit) == (call, limit)
    assert abs(pause.t - t) <= 1.0


# --- the command ----------------------------------------------------------------------

def stores(tmp_path):
    """A HOME holding copies of both fixture trees, and an obs index linking the workers."""
    home = tmp_path / 'home'
    shutil.copytree(CLAUDE_PROJECTS, home / '.claude' / 'projects')
    shutil.copytree(CODEX_SESSIONS, home / '.codex' / 'sessions')
    state = tmp_path / 'state'
    (state / 'obs').mkdir(parents=True)
    index = state / 'obs' / 'index.sqlite'
    db = sqlite3.connect(index)
    db.execute('create table files (file_id integer primary key, harness text, path text)')
    db.execute('create table sessions (file_id integer, harness text, session_id text, parent_session text)')
    parents = json.loads((FIX / 'codex' / 'parents.json').read_text())['parents']
    copied = home / '.codex' / 'sessions' / '2026' / '10' / '10'
    for n, path in enumerate(sorted(copied.iterdir())):
        sid = path.name[-41:-6]
        db.execute('insert into files values (?, ?, ?)', (n, 'codex', str(path)))
        db.execute('insert into sessions values (?, ?, ?, ?)', (n, 'codex', sid, parents.get(sid)))
    db.commit()
    db.close()
    index.chmod(0o444)
    env = {'HOME': str(home), 'XDG_STATE_HOME': str(state), 'PATH': '/usr/bin:/bin'}
    return env, index


class Out:
    def __init__(self):
        self.text = ''

    def write(self, s):
        self.text += s


def cli(argv, env):
    out = Out()
    assert replay.main(argv, env=env, stdout=out) == 0
    return out.text


def test_cli_reports_turns_pauses_and_the_controller_over_a_window(tmp_path):
    env, index = stores(tmp_path)
    before = index.read_bytes()
    text = cli(['2026-10-02T00:00:00Z', '2026-11-01T00:00:00Z'], env)
    assert 'turns: 5 (claude-code 3, codex 2)' in text
    assert 'paused: 0 (0.00 a day over 30 days)' in text
    low = write_limits(tmp_path / 'low.toml', calls=2)
    text = cli(['2026-10-02T00:00:00Z', '2026-11-01T00:00:00Z', '--limits', str(low)], env)
    assert 'paused: 2 (0.07 a day over 30 days)' in text
    assert 'per limit: active 0, calls 2, spawns 0, compactions 0' in text
    assert 'per harness: claude-code 1 (calls 1), codex 1 (calls 1)' in text
    assert (f'sun-fbaf80 controller codex:{CODEX_ID}: turn 2026-10-10T12:00:01Z: paused at '
            '2026-10-10T12:00:05Z by calls (active 0h00m, calls 3, spawns 0, compactions 0)') in text
    assert index.read_bytes() == before


def test_cli_window_drops_turns_outside_it(tmp_path):
    env, _ = stores(tmp_path)
    text = cli(['2026-10-02T00:00:00Z', '2026-10-10T12:20:00Z'], env)
    assert 'turns: 2 (claude-code 1, codex 1)' in text


def test_cli_all_reads_every_record(tmp_path):
    env, _ = stores(tmp_path)
    text = cli(['--all'], env)
    assert 'turns: 5 (claude-code 3, codex 2)' in text
