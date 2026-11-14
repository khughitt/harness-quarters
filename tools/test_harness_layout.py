"""Current layout declarations and finite record-key migration contracts."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools/harness-layout-picks'
CONFIGS = ('claude/settings.json', 'codex/config.toml', 'pi/settings.json', 'agy/settings.json')
RECORDS = {'local/live-picks.json': CONFIGS[:2],
           'local/live-picks-pi.json': CONFIGS[2:3],
           'local/live-picks-agy.json': CONFIGS[3:]}

def env(home):
    return {'PATH': os.environ['PATH'], 'HOME': str(home), 'USER': 'fixture',
            'XDG_CONFIG_HOME': str(home / '.config'), 'XDG_STATE_HOME': str(home / '.state'),
            'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_CONFIG_NOSYSTEM': '1',
            'GIT_AUTHOR_NAME': 'fixture', 'GIT_AUTHOR_EMAIL': 'fixture@example.invalid',
            'GIT_COMMITTER_NAME': 'fixture', 'GIT_COMMITTER_EMAIL': 'fixture@example.invalid',
            'PYTHONDONTWRITEBYTECODE': '1'}


def run(root, environment, *args, check=True, input=None):
    result = subprocess.run(list(map(str, args)), cwd=root, env=environment,
                            input=input, capture_output=True, text=True, timeout=60)
    if check:
        assert result.returncode == 0, result.stderr
    return result


def git(root, environment, *args, **kwargs):
    return run(root, environment, 'git', *args, **kwargs)


def init(tmp_path):
    root, home = tmp_path / 'main', tmp_path / 'home'
    root.mkdir(); home.mkdir()
    environment = env(home)
    git(root, environment, 'init', '-q', '-b', 'main')
    assert Path(git(root, environment, 'rev-parse', '--show-toplevel').stdout.strip()) == root
    assert Path(git(root, environment, 'rev-parse', '--absolute-git-dir').stdout.strip()).is_relative_to(root)
    (root / 'local/codex').mkdir(parents=True)
    (root / 'local/harness-state.lock').touch()
    (root / 'harnesses.toml').write_bytes((ROOT / 'harnesses.toml').read_bytes())
    return root, home, environment


def helper():
    assert TOOL.is_file(), 'the finite record-key command is missing'
    loader = importlib.machinery.SourceFileLoader('layout_picks', str(TOOL))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def rekey(root, environment, direction='forward', apply=True, check=True):
    assert TOOL.is_file(), 'the finite record-key command is missing'
    return run(root, environment, TOOL, '--root', root, '--direction', direction,
               *(['--apply'] if apply else []), check=check)


def saved(root):
    return {name: (root / name).read_bytes() for name in RECORDS if (root / name).exists()}


def seed_records(root):
    for name, keys in RECORDS.items():
        (root / name).write_text(json.dumps({key: {'state': 'default'} for key in keys}) + '\n')
        (root / name).chmod(0o600)


def test_declared_layout_and_filters(tmp_path):
    manifest = tomllib.loads((ROOT / 'harnesses.toml').read_text())
    assert {h['live_state']['config'] for h in manifest['harnesses'].values() if 'live_state' in h} == {
        'harnesses/' + c for c in CONFIGS}
    links = tomllib.loads((ROOT / 'links.toml').read_text())
    assert links['required']['~/.config/ponytail/config.json'] == 'external/ponytail/config.json'
    for old in ('claude', 'codex', 'agy', 'pi', 'ponytail'):
        assert not (ROOT / old).exists()
    environment = env(tmp_path)
    run(ROOT, environment, sys.executable, '.githooks/harness_state.py', 'check')


def test_record_rekey_roundtrip(tmp_path):
    module = helper()
    record = {'codex/config.toml': {'units': [{'state': 'set', 'lines': ['model = "private"\n']},
                                             {'state': 'default'}]}}
    moves = {'codex/config.toml': 'harnesses/codex/config.toml'}
    mapped = module.remap_record(record, moves)
    assert mapped == {'harnesses/codex/config.toml': record['codex/config.toml']}
    assert module.remap_record(mapped, {v: k for k, v in moves.items()}) == record
    root, home, environment = init(tmp_path)
    seed_records(root)
    original = {n: json.loads(b) for n, b in saved(root).items()}
    preview = rekey(root, environment, apply=False)
    assert 'private' not in preview.stdout
    assert {n: json.loads(b) for n, b in saved(root).items()} == original
    rekey(root, environment)
    for name, data in original.items():
        assert json.loads((root / name).read_text()) == {'harnesses/' + k: v for k, v in data.items()}
        assert stat.S_IMODE((root / name).stat().st_mode) == 0o600
    rekey(root, environment, 'reverse')
    assert {n: json.loads(b) for n, b in saved(root).items()} == original


def test_record_rekey_absent_and_repeated(tmp_path):
    root, home, environment = init(tmp_path)
    rekey(root, environment)
    assert saved(root) == {}
    seed_records(root)
    path = root / 'local/live-picks-pi.json'
    path.write_text(path.read_text().replace('pi/settings.json', 'harnesses/pi/settings.json'))
    rekey(root, environment)
    before = {n: ((root / n).stat().st_mtime_ns, b) for n, b in saved(root).items()}
    rekey(root, environment)
    rekey(root, environment, apply=False)
    assert {n: ((root / n).stat().st_mtime_ns, b) for n, b in saved(root).items()} == before


@pytest.mark.parametrize('bad', ['{', '[]', '{"unknown": {}}',
    '{"agy/settings.json": {}, "harnesses/agy/settings.json": {}}',
    '{"agy/settings.json": {}, "agy/settings.json": {}}',
    '{"agy/settings.json": {"x": NaN}}', 'symlink'])
def test_record_rekey_refuses_ambiguity(tmp_path, bad):
    root, home, environment = init(tmp_path)
    seed_records(root)
    path = root / 'local/live-picks-agy.json'
    if bad == 'symlink':
        target = tmp_path / 'outside.json'
        target.write_bytes(path.read_bytes()); path.unlink(); path.symlink_to(target)
    else:
        path.write_text(bad)
    before = saved(root)
    result = rekey(root, environment, check=False)
    assert result.returncode != 0
    assert saved(root) == before


def test_record_rekey_checks_snapshot_before_replace(tmp_path, monkeypatch, capsys):
    module = helper()
    root, home, environment = init(tmp_path)
    seed_records(root)
    changed = root / 'local/live-picks-pi.json'
    replacement = b'{"pi/settings.json": {"state": "set", "values": {"defaultModel": "new"}}}\n'
    real = module.os.replace
    def concurrent_write(source, destination):
        real(source, destination)
        if Path(destination).name == 'live-picks.json':
            changed.write_bytes(replacement)
    monkeypatch.setattr(module.os, 'replace', concurrent_write)
    with pytest.raises(module.Refused, match='changed'):
        module.migrate(root, 'forward', True)
    assert changed.read_bytes() == replacement
    assert 'local/live-picks.json' in capsys.readouterr().out
    assert set(json.loads((root / 'local/live-picks.json').read_text())) == {
        'harnesses/claude/settings.json', 'harnesses/codex/config.toml'}
    monkeypatch.setattr(module.os, 'replace', real)
    rekey(root, environment)
    assert json.loads(changed.read_text())['harnesses/pi/settings.json']['values']['defaultModel'] == 'new'


def test_record_rekey_refuses_worktree_or_subdirectory(tmp_path):
    root, home, environment = init(tmp_path)
    git(root, environment, 'add', 'harnesses.toml')
    git(root, environment, 'commit', '-qm', 'base')
    worktree = tmp_path / 'worktree'
    git(root, environment, 'worktree', 'add', '-qb', 'candidate', worktree)
    for path in (worktree, root / 'local'):
        assert rekey(path, environment, check=False).returncode != 0
