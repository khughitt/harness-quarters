"""The route table reproduces the tracked hook wiring and detects drift."""
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from hook_routes.render import render_live, splice_claude_hooks
from hook_routes.table import load

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / 'harnesses/hook-routes.toml'
CLAUDE = 'harnesses/claude/settings.json'
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


def test_render_reproduces_claude_hooks():
    before = (ROOT / CLAUDE).read_bytes()
    after = render_live(load(TABLE), _tracked_home())[CLAUDE]
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


@pytest.fixture
def checkout(tmp_path):
    home = tmp_path / 'home'
    home.mkdir()
    repo = tmp_path / 'checkout'
    for path in (CLAUDE, CODEX, CODEX_WORK, AGY, SUBSCRIBERS):
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


def test_claude_check_ignores_live_keys(checkout):
    path = checkout[0] / CLAUDE
    settings = json.loads(path.read_bytes())
    settings['model'] = 'test-model'
    path.write_text(json.dumps(settings))
    result = _check(checkout)
    assert result.returncode == 0, result.stderr

    settings['hooks']['SessionStart'][0]['hooks'][0]['command'] = 'different-command'
    path.write_text(json.dumps(settings))
    result = _check(checkout)
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


def test_check_reports_codex_drift(checkout):
    path = checkout[0] / CODEX
    settings = json.loads(path.read_bytes())
    settings['hooks']['SessionStart'].reverse()
    path.write_text(json.dumps(settings, indent=2) + '\n')
    result = _check(checkout)
    assert result.returncode == 1
    assert CODEX in result.stderr


def test_check_reports_a_missing_policy_reference(checkout):
    path = checkout[0] / 'harnesses/hook-routes.toml'
    path.write_text(path.read_text().replace('policies = ["claim-guard"]',
                                             'policies = ["unknown-policy"]'))
    result = _check(checkout)
    assert result.returncode == 1
    assert 'unknown-policy' in result.stderr


def test_check_reports_an_unexpected_claude_event(checkout):
    path = checkout[0] / CLAUDE
    settings = json.loads(path.read_bytes())
    settings['hooks']['UnknownEvent'] = None
    path.write_text(json.dumps(settings))
    result = _check(checkout)
    assert result.returncode == 1
    assert 'UnknownEvent' in result.stderr


def test_check_requires_the_codex_work_destination(checkout):
    root, _ = checkout
    path = root / 'harnesses/hook-routes.toml'
    before, _, tail = path.read_text().partition('[homes.codex-work]')
    _, _, after = tail.partition('[homes.agy]')
    path.write_text(before + '[homes.agy]' + after)

    result = _check(checkout)

    assert result.returncode == 1
    assert CODEX_WORK in result.stderr


def test_check_requires_the_legacy_subscriber_destination(checkout):
    root, _ = checkout
    path = root / 'harnesses/hook-routes.toml'
    alternate = 'relay/alternate.template.json'
    path.write_text(path.read_text().replace(f'output = "{SUBSCRIBERS}"', f'output = "{alternate}"'))
    shutil.copyfile(root / SUBSCRIBERS, root / alternate)

    result = _check(checkout)

    assert result.returncode == 1
    assert SUBSCRIBERS in result.stderr


def test_check_rejects_a_subscriber_role_override(checkout):
    root, _ = checkout
    path = root / 'harnesses/hook-routes.toml'
    path.write_text(path.read_text().replace('{ name = "familiar",',
                                             '{ name = "familiar", role = "guard",'))
    template_path = root / SUBSCRIBERS
    template = json.loads(template_path.read_bytes())
    template['subscribers'][0]['role'] = 'guard'
    template_path.write_text(json.dumps(template, indent=2) + '\n')

    result = _check(checkout)

    assert result.returncode == 1
    assert 'familiar' in result.stderr and 'role' in result.stderr
