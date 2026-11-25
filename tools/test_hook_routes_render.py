"""The route table reproduces the tracked hook wiring and detects drift."""
from dataclasses import replace
from hashlib import sha256
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from hook_routes.render import render_live, render_next, splice_claude_hooks, subscriber_bytes
from hook_routes.table import TargetSubscriberFile, load
from test_hook_routes_relay import runtime, shared_table  # noqa: F401  (runtime is a pytest fixture)

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / 'harnesses/hook-routes.toml'
CLAUDE = 'harnesses/claude/settings.json'
CLAUDE_WORK = 'harnesses/claude/work/settings.json'
CODEX = 'harnesses/codex/hooks.json'
CODEX_WORK = 'harnesses/codex/work/hooks.json'
AGY = 'harnesses/agy/hooks.json'
SUBSCRIBERS = 'relay/subscribers.template.json'


def _tracked_home():
    # Hosted CI has a different home from the committed relay paths.
    session = json.loads((ROOT / CODEX).read_bytes())['hooks']['SessionStart']
    relay_path = Path(shlex.split(session[-1]['hooks'][0]['command'])[1])
    return next(parent.parent for parent in relay_path.parents if parent.name == '.local')


def test_render_reproduces_codex_and_agy_files():
    home = Path.home()
    tracked_home = _tracked_home()
    rendered = render_live(load(TABLE), home if home == tracked_home else tracked_home)
    for path in (CODEX, CODEX_WORK, AGY):
        assert rendered[path] == (ROOT / path).read_bytes()


@pytest.mark.parametrize('path', [CLAUDE, CLAUDE_WORK])
def test_render_reproduces_claude_hooks(path):
    before = (ROOT / path).read_bytes()
    after = render_live(load(TABLE), _tracked_home())[path]
    assert json.loads(after)['hooks'] == json.loads(before)['hooks']
    # The checked-in hooks already use the renderer's indentation.
    assert after == before


def test_splice_preserves_noncanonical_bytes():
    prefix = '{\r\n  "z" : {"hooks": ["nested"]},\r\n  "hooks"  : '
    suffix = ',\r\n  "a": "text with a }"  \r\n}\r\n'
    before = prefix + '{ "Old":["é]"] }' + suffix
    assert splice_claude_hooks(before, {'New': []}) == prefix + '{\n    "New": []\n  }' + suffix


def test_render_reproduces_subscriber_template():
    rendered = render_live(load(TABLE), Path.home())
    assert rendered[SUBSCRIBERS] == (ROOT / SUBSCRIBERS).read_bytes()


def schema_3(table, search_path=('~/.local/bin', '/usr/bin')):
    """The table with a relay whose subscriber files are schema 3 behind the live runtime's name."""
    runtimes = {**table.runtimes, 'v0.5.0': replace(table.runtimes['v0.5.0'], subscriber_schema=3)}
    return replace(table, runtimes=runtimes, search_path=search_path)


@pytest.mark.parametrize('home, listed', [(None, '@HOME@/.local/bin'), (Path('/h'), '/h/.local/bin')])
def test_schema_3_runtime_renders_the_search_path(home, listed):
    table = shared_table()
    source = table.subscriber_files[table.reconciliation_file]
    before = json.loads(subscriber_bytes(table, source, home))
    after = json.loads(subscriber_bytes(schema_3(table), source, home))
    assert list(after) == ['schema', 'searchPath', 'subscribers']
    assert after == {**before, 'schema': 3, 'searchPath': [listed, '/usr/bin']}
    # The same list says nothing to a runtime that reads schema 2.
    assert json.loads(subscriber_bytes(replace(table, search_path=('/usr/bin',)), source, home)) == before
    assert before['schema'] == 2 and 'searchPath' not in before


def test_a_target_file_keeps_its_runtimes_schema(tmp_path):
    table = schema_3(shared_table())
    source = table.subscriber_files[table.reconciliation_file]
    home = table.homes['codex']
    index, binding = next((i, b) for i, b in enumerate(home.bindings) if b.event == 'UserPromptSubmit' and b.lines[0].kind == 'relay')
    moved = replace(binding, next=(replace(binding.lines[0], subscriber_file='candidate'),))
    bindings = (*home.bindings[:index], moved, *home.bindings[index + 1:])
    table = replace(table, homes={'codex': replace(home, bindings=bindings)},
                    target_files={'candidate': TargetSubscriberFile('v0.5.0', source.subscribers)})
    rendered = render_next(table, tmp_path)
    address, = (name for name in rendered if name.startswith('v0.5.0-'))
    data = json.loads(rendered[address])
    assert data['schema'] == 3 and data['searchPath'] == [f'{tmp_path}/.local/bin', '/usr/bin']
    assert address.startswith('v0.5.0-' + sha256(rendered[address]).hexdigest()[:12])
    command = json.loads(rendered[CODEX])['hooks']['UserPromptSubmit'][0]['hooks'][0]['command']
    assert shlex.split(command)[-2] == f'{tmp_path}/.config/relay/{address}'


def edited_table(tmp_path, *changes):
    text = TABLE.read_text()
    for before, after in changes:
        assert before in text
        text = text.replace(before, after)
    path = tmp_path / 'harnesses/hook-routes.toml'
    path.parent.mkdir(parents=True)
    path.write_text(text)
    return path


RUNTIME = '[runtimes."v0.5.0"]\n'


def declared(entries):
    """The tracked search_path line, replaced."""
    current = next(line for line in TABLE.read_text().splitlines() if line.startswith('search_path = '))
    return current, '' if entries is None else f'search_path = {json.dumps(entries)}'


def test_a_schema_3_runtime_needs_a_search_path(tmp_path):
    current, removed = declared(None)
    path = edited_table(tmp_path, (RUNTIME, RUNTIME + 'subscriber_schema = 3\n'), (current, removed))
    with pytest.raises(ValueError, match='search_path'):
        load(path)
    path.write_text(path.read_text().replace('subscriber_schema = 3\n', ''))
    load(path)


@pytest.mark.parametrize('entries', [
    ['bin'], ['./bin'], ['$HOME/bin'], ['~'], ['~other/bin'], [''], [7],
    ['~/bin', '~/bin'], ['/usr/bin/'], ['/usr//bin'], ['//usr/bin'], ['/usr/../bin'], ['~/bin/'], ['~/../bin'], ['/a:b'],
])
def test_a_search_path_relay_would_refuse_is_refused(tmp_path, entries):
    with pytest.raises(ValueError, match='search_path'):
        load(edited_table(tmp_path, declared(entries)))


def test_a_search_path_is_distinct_once_home_is_expanded(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', '/h')
    path = edited_table(tmp_path, declared(['~/bin', '/h/bin']))
    with pytest.raises(ValueError, match='search_path'):
        load(path)
    monkeypatch.setenv('HOME', '/other')
    assert load(path).search_path == ('~/bin', '/h/bin')


@pytest.mark.parametrize('schema', ['1', '4', '"3"', 'true'])
def test_an_unknown_subscriber_schema_is_refused(tmp_path, schema):
    with pytest.raises(ValueError, match='subscriber_schema'):
        load(edited_table(tmp_path, (RUNTIME, f'{RUNTIME}subscriber_schema = {schema}\n')))


def test_a_path_file_cannot_bind_a_schema_3_runtime(tmp_path):
    pinned = '[subscriber_files."shared-v0.5.0-retired-guard"]\nruntime = "v0.5.0"\n'
    by_path = pinned.replace('runtime = "v0.5.0"', 'path = "~/.config/relay/v0.5.0/relay/subscribers.json"')
    load(edited_table(tmp_path / 'schema-2', (pinned, by_path)))
    path = edited_table(tmp_path / 'schema-3', (pinned, by_path), (RUNTIME, RUNTIME + 'subscriber_schema = 3\n'))
    with pytest.raises(ValueError, match='schema 3'):
        load(path)


@pytest.fixture
def checkout(tmp_path):
    home = tmp_path / 'home'
    home.mkdir()
    repo = tmp_path / 'checkout'
    for path in (CLAUDE, CLAUDE_WORK, CODEX, CODEX_WORK, AGY, SUBSCRIBERS):
        dest = repo / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / path, dest)
    shutil.copy(TABLE, repo / 'harnesses')
    for path, data in render_live(load(repo / 'harnesses/hook-routes.toml'), home).items():
        (repo / path).write_bytes(data)
    shutil.copytree(ROOT / 'tools/hook_routes', repo / 'tools/hook_routes',
                    ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy(ROOT / 'tools/hook-routes', repo / 'tools')
    return repo, home


def _check(checkout):
    repo, home = checkout
    return subprocess.run([sys.executable, str(repo / 'tools/hook-routes'), 'check'],
                          env={'PATH': os.environ['PATH'], 'HOME': str(home)},
                          cwd=repo, capture_output=True, text=True)


@pytest.fixture
def qualified_checkout(checkout, runtime):
    """The checkout with the pinned relay and fixture qualification records for its HOME.

    The tracked records bind each subscriber file's sha256 as expanded for the
    account HOME, so they cannot match the temporary HOME. These copies are
    fixture records: identical except for configDigest, rewritten to the digest
    of the file each qualified line runs under the temporary HOME.
    """
    repo, home = checkout
    installs = home / '.local/share/relay'
    installs.mkdir(parents=True)
    (installs / 'v0.5.0').symlink_to(runtime.parents[1], target_is_directory=True)
    records = repo / 'harnesses/qualification'
    shutil.copytree(ROOT / 'harnesses/qualification', records)
    table = load(repo / 'harnesses/hook-routes.toml')
    digests = {}
    for _, _, _, binding in table.bindings():
        for line in (line for line in binding.lines if line.kind == 'relay'):
            data = subscriber_bytes(table, table.subscriber_files[line.subscriber_file], home)
            for policy in line.policies:
                state = table.policy_state(policy, line)
                for name in state.records if state and state.kind == 'relay' else ():
                    digests.setdefault(name, set()).add(sha256(data).hexdigest())
    assert digests, 'the live table names no qualified relay line'
    for name, (digest, *conflict) in digests.items():
        assert not conflict, f'{name} would need two config digests'
        path = records / name
        path.write_text(json.dumps(dict(json.loads(path.read_bytes()), configDigest=digest)))
    return repo, home


def test_claude_check_ignores_live_keys(qualified_checkout):
    path = qualified_checkout[0] / CLAUDE
    settings = json.loads(path.read_bytes())
    settings['model'] = 'test-model'
    path.write_text(json.dumps(settings))
    result = _check(qualified_checkout)
    assert result.returncode == 0, result.stderr

    settings['hooks']['SessionStart'][0]['hooks'][0]['command'] = 'different-command'
    path.write_text(json.dumps(settings))
    result = _check(qualified_checkout)
    assert result.returncode == 1
    assert CLAUDE in result.stderr and 'SessionStart' in result.stderr


def test_promoted_preflight_refuses_settings_rendered_for_another_home(checkout):
    repo, home = checkout
    other_home = home.with_name('other-home')
    other_home.mkdir()
    result = subprocess.run([sys.executable, str(repo / 'tools/hook-routes'), 'preflight'],
                            env={'PATH': os.defpath, 'HOME': str(other_home)},
                            cwd=repo, capture_output=True, text=True)
    assert result.returncode == 1
    assert CODEX in result.stderr and 'hook-drift' in result.stderr


def test_qualified_checkout_passes_unmodified(qualified_checkout):
    # The negative checks below rely on this baseline: only their drift fails.
    result = _check(qualified_checkout)
    assert result.returncode == 0, result.stderr


def test_check_reports_codex_drift(qualified_checkout):
    path = qualified_checkout[0] / CODEX
    settings = json.loads(path.read_bytes())
    settings['hooks']['SessionStart'].reverse()
    path.write_text(json.dumps(settings, indent=2) + '\n')
    result = _check(qualified_checkout)
    assert result.returncode == 1
    assert CODEX in result.stderr


def test_check_reports_a_missing_policy_reference(qualified_checkout):
    path = qualified_checkout[0] / 'harnesses/hook-routes.toml'
    path.write_text(path.read_text().replace('policies = ["claim-guard"]',
                                             'policies = ["unknown-policy"]'))
    result = _check(qualified_checkout)
    assert result.returncode == 1
    assert 'unknown-policy' in result.stderr


def test_check_reports_an_unexpected_claude_event(qualified_checkout):
    path = qualified_checkout[0] / CLAUDE
    settings = json.loads(path.read_bytes())
    settings['hooks']['UnknownEvent'] = None
    path.write_text(json.dumps(settings))
    result = _check(qualified_checkout)
    assert result.returncode == 1
    assert 'UnknownEvent' in result.stderr


def test_check_requires_the_codex_work_destination(qualified_checkout):
    root, _ = qualified_checkout
    path = root / 'harnesses/hook-routes.toml'
    before, _, tail = path.read_text().partition('[homes.codex-work]')
    _, _, after = tail.partition('[homes.agy]')
    path.write_text(before + '[homes.agy]' + after)

    result = _check(qualified_checkout)

    assert result.returncode == 1
    assert CODEX_WORK in result.stderr


def test_check_requires_the_legacy_subscriber_destination(qualified_checkout):
    root, _ = qualified_checkout
    path = root / 'harnesses/hook-routes.toml'
    alternate = 'relay/alternate.template.json'
    path.write_text(path.read_text().replace(f'output = "{SUBSCRIBERS}"', f'output = "{alternate}"'))
    shutil.copyfile(root / SUBSCRIBERS, root / alternate)

    result = _check(qualified_checkout)

    assert result.returncode == 1
    assert SUBSCRIBERS in result.stderr


def test_check_rejects_a_subscriber_role_override(qualified_checkout):
    root, _ = qualified_checkout
    path = root / 'harnesses/hook-routes.toml'
    path.write_text(path.read_text().replace('{ name = "familiar",',
                                             '{ name = "familiar", role = "guard",'))
    template_path = root / SUBSCRIBERS
    template = json.loads(template_path.read_bytes())
    template['subscribers'][0]['role'] = 'guard'
    template_path.write_text(json.dumps(template, indent=2) + '\n')

    result = _check(qualified_checkout)

    assert result.returncode == 1
    assert 'familiar' in result.stderr and 'role' in result.stderr


def test_ask_line_renders_relay_ask_command_and_validates_shape(tmp_path):
    from hook_routes.table import Binding, Line, RouteState

    table = shared_table()
    home = tmp_path / 'home'
    state = RouteState('ask', owner='relay-f58531', evidence='relay:docs/evidence/claude-code-answer-routes.json@2.1.332')
    pre = Binding('PreToolUse', 'AskUserQuestion', (Line(('claude-ask',), runtime='v0.7.0', ask=True, handback=True, timeout=86400),))
    post = Binding('PostToolUse', 'AskUserQuestion', (Line(('claude-ask',), runtime='v0.7.0', ask=True, timeout=10),))
    claude = replace(table.homes['claude'], bindings=(pre, post))
    configured = replace(table, states={**table.states, 'claude-ask': state}, homes={**table.homes, 'claude': claude})
    hooks = json.loads(render_live(configured, home)[CLAUDE])['hooks']
    script = f"'{home}/.local/share/relay/v0.7.0/node_modules/relay/bin/relay.js'"
    assert hooks['PreToolUse'] == [{
        'matcher': 'AskUserQuestion',
        'hooks': [{'type': 'command', 'command': f"'/usr/bin/node' {script} ask --harness claude-code --handback PreToolUse", 'timeout': 86400}],
    }]
    assert hooks['PostToolUse'] == [{
        'matcher': 'AskUserQuestion',
        'hooks': [{'type': 'command', 'command': f"'/usr/bin/node' {script} ask --harness claude-code PostToolUse", 'timeout': 10}],
    }]
    for bad in [
        '[homes.codex]\nharness = "codex"\npath = "harnesses/codex/hooks.json"\nbindings = [\n  { event = "PreToolUse", matcher = "AskUserQuestion", lines = [{ policies = ["claude-ask"], runtime = "v0.7.0", ask = true, timeout = 86400 }] },',
        '  { event = "PostToolUse", matcher = "AskUserQuestion", lines = [{ policies = ["claude-ask"], runtime = "v0.7.0", ask = true, handback = true, timeout = 10 }] },',
        '  { event = "PreToolUse", matcher = "*", lines = [{ policies = ["claude-ask"], runtime = "v0.7.0", ask = true, timeout = 86400 }] },',
        '  { event = "PreToolUse", matcher = "AskUserQuestion", lines = [{ policies = ["claude-ask"], command = "echo", handback = true }] },',
    ]:
        base = '[states.claude-ask]\nstate = "ask"\nowner = "relay-f58531"\nevidence = "probe"\n\n'
        target = '[homes.codex]\nharness = "codex"\npath = "harnesses/codex/hooks.json"\nbindings = [' if bad.startswith('[homes.codex]') else '  { event = "SessionStart", matcher = "startup|resume", lines = [{ policies = ["tasks-notices"], command = "tasks notices --pretty", timeout = 5 }] },'
        replacement = bad if bad.startswith('[homes.codex]') else f'{target}\n{bad}'
        path = edited_table(tmp_path / str(abs(hash(bad))), ('[states.claude-sessionstart]\n', base + '[states.claude-sessionstart]\n'), (target, replacement))
        with pytest.raises(ValueError, match='ask|handback'):
            load(path)
