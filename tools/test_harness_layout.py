"""The one-time layout transition, using real hooks in isolated main checkouts."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[1]
OLD = 'e015ff4fd063d4a001796934816d67e8676c83b8'
TOOL = ROOT / 'tools/harness-layout-picks'
CONFIGS = ('claude/settings.json', 'codex/config.toml', 'pi/settings.json', 'agy/settings.json')
RECORDS = {'local/live-picks.json': CONFIGS[:2],
           'local/live-picks-pi.json': CONFIGS[2:3],
           'local/live-picks-agy.json': CONFIGS[3:]}
HOOKS = ('harness_state.py', 'harness-state-clean', 'codex-trust', 'live-picks',
         'harness-state-refresh', 'post-checkout', 'post-merge', 'post-rewrite')
FILES = (*CONFIGS, 'codex/hooks.json', 'codex/work/hooks.json', 'agy/hooks.json',
         'agy/skills.json', 'pi/bin/pi', 'pi/extensions/harness-state.ts', 'ponytail/config.json')


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


def moved(name):
    return ('external/' if name.startswith('ponytail/') else 'harnesses/') + name


def fixture_links(text):
    """Real target values; omit unrelated owner projects from this small fixture."""
    data = tomllib.loads(text)
    lines = ['[required]', '"~/.config/ponytail/config.json" = ' + json.dumps(
        data['required']['~/.config/ponytail/config.json'])]
    selected = {'claude': ['settings.json'], 'codex': ['config.toml', 'hooks.json'],
                'codex-work': ['hooks.json'], 'pi': ['settings.json', 'extensions/harness-state.ts'],
                'agy': ['settings.json'], 'agy-config': ['hooks.json', 'skills.json']}
    for name, keys in selected.items():
        table = data['harness'][name]
        lines += [f'[harness.{name}]', f'home = {json.dumps(table["home"])}']
        for key in ('adopt', 'anchors'):
            if key in table:
                lines += [f'{key} = {json.dumps(table[key])}']
        lines += [f'[harness.{name}.links]']
        lines += [f'{json.dumps(k)} = {json.dumps(table["links"][k])}' for k in keys]
    return '\n'.join(lines) + '\n'


class World:
    def __init__(self, tmp_path):
        assert (ROOT / 'harnesses').is_dir(), 'candidate layout is not implemented'
        self.root, self.home, self.env = init(tmp_path)
        self.names = ['harnesses.toml', '.gitattributes', 'tools/harness-links',
                      *['.githooks/' + name for name in HOOKS], *FILES]
        for name in self.names:
            self.put(name, self.old(name))
        self.put('links.toml', fixture_links(self.old('links.toml').decode()).encode())
        self.put('.gitignore', b'local/\n__pycache__/\n')
        for key, value in [('core.hooksPath', '.githooks'), ('filter.harness-state.clean', '.githooks/harness-state-clean %f'),
                           ('filter.harness-state.smudge', 'cat'), ('filter.harness-state.required', 'true')]:
            self.git('config', key, value)
        self.git('add', '-A'); self.git('commit', '-qm', 'old layout')
        self.before = self.git('rev-parse', 'HEAD').stdout.strip()
        self.git('switch', '-qc', 'candidate')
        self.git('rm', '-q', '--', *FILES)
        for name in self.names:
            target = moved(name) if name in FILES else name
            self.put(target, (ROOT / target).read_bytes())
        self.put('links.toml', fixture_links((ROOT / 'links.toml').read_text()).encode())
        self.put('docs/notes/review.md', b'review history must survive rollback\n')
        self.git('add', '-A'); self.git('commit', '-qm', 'candidate layout')
        self.reviewed = self.git('rev-parse', 'HEAD').stdout.strip()
        self.git('switch', '-q', 'main')
        for name in ('.claude', '.codex', '.codex-work', '.pi/agent', '.gemini/antigravity-cli', '.gemini/config'):
            (self.home / name).mkdir(parents=True, exist_ok=True)
        self.link('--apply')

    def old(self, name):
        return git(ROOT, self.env, 'show', f'{OLD}:{name}').stdout.encode()

    def put(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        if name.startswith('.githooks/') or name in ('tools/harness-links', 'pi/bin/pi', 'harnesses/pi/bin/pi'):
            path.chmod(0o755)

    def git(self, *args, **kwargs):
        return git(self.root, self.env, *args, **kwargs)

    def hook(self, name, *args):
        result = run(self.root, self.env, self.root / '.githooks' / name, *args)
        assert not result.stderr, result.stderr
        return result

    def link(self, *args, check=True):
        return run(self.root, self.env, self.root / 'tools/harness-links', *args, check=check)

    def seed(self):
        for name, picks in [('claude/settings.json', {'model': 'fixture-claude', 'effortLevel': 'high'}),
                            ('pi/settings.json', {'defaultProvider': 'fixture', 'defaultModel': 'fixture-pi', 'defaultThinkingLevel': 'high'}),
                            ('agy/settings.json', {'model': 'fixture-agy', 'effort': 'high'})]:
            path = self.root / name
            path.write_text(json.dumps({**json.loads(path.read_text()), **picks}, indent=2) + '\n')
        path = self.root / 'codex/config.toml'
        path.write_text('model = "fixture-codex"\nmodel_reasoning_effort = "high"\n' + path.read_text()
                        + '[projects."/fixture/project"]\ntrust_level = "trusted"\n')
        self.hook('codex-trust', 'sync'); self.hook('live-picks', 'sync')
        self.trust = (self.root / 'local/codex/trust.toml').read_bytes()
        self.hook_state = tomllib.loads(path.read_text()).get('hooks', {}).get('state')

    def carry(self):
        path = self.root / 'agy/settings.json'
        path.write_text(json.dumps({**json.loads(path.read_text()), 'agentMode': 'auto'}, indent=2) + '\n')
        path = self.root / 'codex/config.toml'
        path.write_text('layout_local = true\n' + path.read_text())
        self.patch = self.git('diff', '--binary', '--', *CONFIGS).stdout
        assert 'agentMode' in self.patch and 'layout_local' in self.patch

    def transition(self):
        self.hook('codex-trust', 'sync'); self.hook('live-picks', 'sync')
        assert (self.home / '.gemini/antigravity-cli/settings.json').is_symlink()
        self.git('restore', '--source=' + self.before, '--worktree', '--', *CONFIGS)
        rekey(self.root, self.env)
        merged = self.git('merge', '--ff-only', self.reviewed)
        assert not merged.stderr, merged.stderr
        # Prove the real post-merge hooks consumed the migrated keys before git apply.
        assert json.loads((self.root / 'harnesses/agy/settings.json').read_text())['model'] == 'fixture-agy'
        assert tomllib.loads((self.root / 'harnesses/codex/config.toml').read_text())['model'] == 'fixture-codex'
        self.git('apply', '--check', '--directory=harnesses', '-', input=self.patch)
        self.git('apply', '--directory=harnesses', '-', input=self.patch)
        self.link('--apply')
        self.hook('codex-trust', 'sync'); self.hook('live-picks', 'sync')
        self.verify()

    def verify(self):
        self.link('--check')
        assert self.git('diff', '--cached', '--name-only').stdout == ''
        before, after = self.root.parent / 'before.patch', self.root.parent / 'after.patch'
        before.write_text(self.patch)
        after.write_text(self.git('diff', '--binary', '--relative=harnesses', '--', *[moved(c) for c in CONFIGS]).stdout)
        doc_run(self, 'compare-patches', before, after)
        assert json.loads((self.root / 'harnesses/agy/settings.json').read_text())['agentMode'] == 'auto'
        assert json.loads((self.root / 'harnesses/claude/settings.json').read_text())['model'] == 'fixture-claude'
        assert json.loads((self.root / 'harnesses/pi/settings.json').read_text())['defaultModel'] == 'fixture-pi'
        config = tomllib.loads((self.root / 'harnesses/codex/config.toml').read_text())
        assert config['model'] == 'fixture-codex' and config['model_reasoning_effort'] == 'high'
        assert config['projects']['/fixture/project']['trust_level'] == 'trusted'
        assert config.get('hooks', {}).get('state') == self.hook_state
        assert (self.root / 'local/codex/trust.toml').read_bytes() == self.trust


def test_initiating_host_transition(tmp_path):
    world = World(tmp_path)
    world.seed(); world.carry()
    detached = world.home / '.gemini/antigravity-cli/settings.json'
    raw = detached.read_bytes()
    detached.unlink(); detached.write_bytes(raw)
    assert not detached.is_symlink()
    world.transition()
    assert detached.is_symlink()
    for name in ('agy', 'claude', 'codex', 'pi', 'ponytail'):
        assert not (world.root / name).exists()


def runbook_script(name):
    text = (ROOT / 'docs/runbooks/harness-layout.md').read_text()
    section = text.split(f'<!-- script:{name} -->\n```python\n', 1)[1]
    return section.split('\n```', 1)[0]


def doc_run(world, name, *args, check=True):
    return run(world.root, world.env, sys.executable, '-c', runbook_script(name), *args, check=check)


def test_post_sync_detached_agy_transition(tmp_path):
    world = World(tmp_path)
    world.seed()
    detached = world.home / '.gemini/antigravity-cli/settings.json'
    data = json.loads(detached.read_text()); data.update(agentMode='auto', model='detached-choice')
    detached.unlink(); detached.write_text(json.dumps(data, indent=2) + '\n')
    original = tmp_path / 'detached.json'; original.write_bytes(detached.read_bytes())
    base = tmp_path / 'old-agy.json'; base.write_bytes(world.old('agy/settings.json'))
    # Refresh filtered index stat data before simulating arrival of the new tree.
    world.git('add', '--', *CONFIGS)
    assert world.git('diff', '--cached', '--name-only').stdout == ''
    rekey(world.root, world.env)
    world.git('merge', '--ff-only', world.reviewed)
    current = world.root / 'harnesses/agy/settings.json'
    data = json.loads(current.read_text()); data['newTrackedSetting'] = True
    current.write_text(json.dumps(data, indent=2) + '\n')
    assert current.stat().st_mtime_ns > detached.stat().st_mtime_ns
    refusal = world.link('--apply', check=False)
    assert refusal.returncode != 0 and 'first-run' in refusal.stdout
    world.hook('live-picks', 'sync')
    assert not detached.is_symlink()  # old anchors prevent adoption
    doc_run(world, 'repair-anchors', world.root)
    doc_run(world, 'align-agy', world.root, base, original)
    world.hook('live-picks', 'sync')
    world.link('--apply'); world.link('--check')
    assert detached.is_symlink()
    final = json.loads(current.read_text())
    assert (final['model'], final['agentMode'], final['newTrackedSetting']) == ('detached-choice', 'auto', True)
    assert json.loads(original.read_text())['agentMode'] == 'auto'


@pytest.mark.parametrize('anchor_name', ['hooks.json', 'skills.json'])
def test_activation_refuses_unowned_or_changing_inputs(tmp_path, anchor_name):
    world = World(tmp_path)
    world.seed()
    world.git('add', '--', *CONFIGS)
    rekey(world.root, world.env)
    world.git('merge', '--ff-only', world.reviewed)
    anchor = world.home / '.gemini/config' / anchor_name
    anchor.unlink(); anchor.symlink_to(tmp_path / 'foreign/hooks.json')
    anchors = [world.home / '.gemini/config' / n for n in ('hooks.json', 'skills.json')]
    before = [os.readlink(p) for p in anchors]
    result = doc_run(world, 'repair-anchors', world.root, check=False)
    assert result.returncode != 0 and 'ownership' in result.stderr
    assert [os.readlink(p) for p in anchors] == before
    checkpoint = tmp_path / 'checkpoint.json'
    guarded = world.root / 'harnesses/agy/settings.json'
    doc_run(world, 'guard', 'save', checkpoint, guarded, anchor)
    original = checkpoint.read_bytes()
    guarded.write_text(guarded.read_text() + ' ')
    result = doc_run(world, 'guard', 'check', checkpoint, check=False)
    assert result.returncode != 0
    assert checkpoint.read_bytes() == original


def test_ignored_contents_and_rollback(tmp_path):
    world = World(tmp_path)
    world.seed(); world.carry()
    # Pre-merge recovery: reverse records, reapply only the saved unfiltered patch.
    world.git('restore', '--source=' + world.before, '--worktree', '--', *CONFIGS)
    rekey(world.root, world.env); rekey(world.root, world.env, 'reverse')
    world.git('apply', '--check', '-', input=world.patch)
    world.git('apply', '-', input=world.patch)
    world.hook('codex-trust', 'sync'); world.hook('live-picks', 'sync')
    assert world.git('diff', '--binary', '--', *CONFIGS).stdout == world.patch
    unique = world.root / 'claude/local-note.txt'; unique.write_bytes(b'unique operator note\n')
    cache = world.root / 'claude/__pycache__/probe.pyc'; cache.parent.mkdir(); cache.write_bytes(b'regenerable')
    world.transition()
    destination = world.root / 'harnesses/claude/local-note.txt'
    assert not destination.exists()
    unique.rename(destination); assert destination.read_bytes() == b'unique operator note\n'
    cache.unlink(); cache.parent.rmdir(); (world.root / 'claude').rmdir()
    assert all(not (world.root / n).exists() for n in ('agy', 'claude', 'codex', 'pi', 'ponytail'))
    # Corrective commit, preserving newly committed review history.
    world.git('restore', '--source=' + world.reviewed, '--worktree', '--', *[moved(c) for c in CONFIGS])
    rekey(world.root, world.env, 'reverse')
    runtime = ['harnesses.toml', '.gitattributes', 'links.toml', '.githooks', 'tools/harness-links',
               *FILES, *[moved(n) for n in FILES]]
    world.git('restore', '--source=' + world.before, '--staged', '--worktree', '--', *runtime)
    world.git('commit', '-qm', 'fix: restore prior runtime layout')
    destination.rename(world.root / 'claude/local-note.txt')
    for name in ('harnesses/claude', 'harnesses', 'external'):
        path = world.root / name
        if path.exists():
            path.rmdir()
    assert not (world.root / 'harnesses').exists() and not (world.root / 'external').exists()
    world.git('apply', '--check', '-', input=world.patch); world.git('apply', '-', input=world.patch)
    doc_run(world, 'repair-anchors', world.root, 'reverse')
    world.link('--apply'); world.hook('codex-trust', 'sync'); world.hook('live-picks', 'sync')
    world.link('--check')
    assert (world.root / 'docs/notes/review.md').is_file()
    assert world.git('diff', '--binary', '--', *CONFIGS).stdout == world.patch
    assert (world.root / 'claude/local-note.txt').read_bytes() == b'unique operator note\n'


def test_codex_hook_bytes_and_trust_unchanged(tmp_path):
    world = World(tmp_path)
    world.seed(); world.carry(); world.transition()
    for name, home in [('codex/hooks.json', '.codex'), ('codex/work/hooks.json', '.codex-work')]:
        assert (world.root / moved(name)).read_bytes() == world.old(name)
        assert (world.home / home / 'hooks.json').resolve() == world.root / moved(name)


def test_patch_comparison_preserves_changes_and_context(tmp_path):
    before, after = tmp_path / 'before.patch', tmp_path / 'after.patch'
    before.write_text('diff --git a/a b/a\nindex 1111111..2222222 100644\n@@ -1 +1 @@\n-old\n+new\n')
    after.write_text(before.read_text().replace('1111111..2222222', '3333333..4444444'))
    command = [sys.executable, '-c', runbook_script('compare-patches'), before, after]
    run(tmp_path, env(tmp_path), *command)
    after.write_text(after.read_text().replace('+new', '+lost'))
    assert run(tmp_path, env(tmp_path), *command, check=False).returncode != 0


def test_post_sync_conflict_keeps_both_versions(tmp_path):
    world = World(tmp_path)
    world.seed()
    base = tmp_path / 'old-agy.json'; base.write_bytes(world.old('agy/settings.json'))
    home_data = json.loads((world.root / 'agy/settings.json').read_text())
    world.git('add', '--', *CONFIGS)
    rekey(world.root, world.env); world.git('merge', '--ff-only', world.reviewed)
    current = world.root / 'harnesses/agy/settings.json'
    current.write_text(json.dumps({**json.loads(current.read_text()), 'setting': 'tracked-change'}))
    detached = world.home / '.gemini/antigravity-cli/settings.json'
    detached.unlink(); detached.write_text(json.dumps({**home_data, 'setting': 'detached-change'}))
    snapshot = tmp_path / 'detached.json'; snapshot.write_bytes(detached.read_bytes())
    before = current.read_bytes(), detached.read_bytes()
    result = doc_run(world, 'align-agy', world.root, base, snapshot, check=False)
    assert result.returncode != 0 and 'conflict' in result.stderr
    assert (current.read_bytes(), detached.read_bytes()) == before
