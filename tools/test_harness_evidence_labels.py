"""Catch lost origin evidence, inferred human authorship and missed native conflicts."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib

import pytest

from harness_evidence import lines, records
from harness_evidence_testing import FIXTURES, PATHS

CATALOGUE = tomllib.loads((FIXTURES / 'CATALOGUE.toml').read_text())['sample']
CORPUS = [s for s in CATALOGUE if 'expected' in s]


def expected_origin(evidence):
    # Only nullable fields may be omitted by TOML's lack of null.
    assert {'flags', 'markers', 'unrecognized_tag'} <= evidence.keys()
    assert evidence.keys() <= {'native_kind', 'flags', 'markers', 'unrecognized_tag'}
    assert evidence['unrecognized_tag'].keys() == {'lead', 'joined'}
    assert all(type(value) is bool for value in evidence['unrecognized_tag'].values())
    markers = []
    for marker in evidence['markers']:
        assert 'name' in marker and marker.keys() <= {'name', 'lead', 'joined'}
        assert all(marker.get(key) in {None, 'start', 'inside'} for key in ('lead', 'joined'))
        markers.append({'name': marker['name'], 'lead': marker.get('lead'), 'joined': marker.get('joined')})
    return {'native_kind': evidence.get('native_kind'), 'flags': evidence['flags'],
            'markers': markers, 'unrecognized_tag': evidence['unrecognized_tag']}


def read_sample(sample):
    path = FIXTURES / sample['path']
    place = lines.Place(sample['harness'], 'file', None, 'explicit', sample['path'], path)
    fmt = lines.detect_format(path, path.stat().st_size)
    if fmt == 'sdk':
        return records.sdk_read(place, path.stat().st_size)
    if fmt == 'claude':
        return records.claude_read(place, path.stat().st_size)
    return records.codex_read(place, path.stat().st_size, lambda _id: None)


def prompt_record(sample):
    return next(r for r in read_sample(sample).records if 'prompt' in r['_flags'])


@pytest.mark.parametrize('sample', CORPUS, ids=lambda s: Path(s['path']).stem)
def test_origin_evidence_and_label_match_catalogue(sample):
    record = prompt_record(sample)
    assert record['origin'] == expected_origin(sample['expected']['evidence'])
    assert [record['role'], record['basis']] == sample['expected']['label']
    assert record['rule'] == record['role_basis']


def test_conflicts_are_unknown_with_their_evidence():
    for sample in CORPUS:
        if 'conflict-' not in sample['path']:
            continue
        record = prompt_record(sample)
        assert (record['role'], record['rule'], record['basis']) == ('unknown', 'conflict', 'heuristic')
        assert len(record['conflict']) == 2
        assert record['conflict'][0] == {'native_kind': record['origin']['native_kind']}
        assert record['conflict'][1]['markers'] == record['origin']['markers']


def test_every_rule_has_a_basis_and_no_fallback_claims_human():
    for sample in CATALOGUE:
        if sample.get('profile') == 'index':
            continue
        for record in read_sample(sample).records:
            assert record['basis'] in {'native', 'convention', 'heuristic'}
            assert record['rule'] == record['role_basis']
            if record['role'] == 'human':
                assert record['basis'] in {'native', 'convention'}
            if record['rule'] == 'prefix_rule' and record['role'] != 'dispatch':
                assert record['role'] in {'injected', 'user_channel_unattributed', 'unknown'}


def test_catalogue_covers_all_samples_without_claiming_live_provenance():
    assert {sample['path'] for sample in CATALOGUE} == {
        str(p.relative_to(FIXTURES)) for p in FIXTURES.rglob('*.jsonl')}
    assert len({sample['path'] for sample in CATALOGUE}) == len(CATALOGUE)
    assert all(s['version'] and s['provenance'] == 'synthetic'
               for s in CATALOGUE if s['path'] != 'pi/sanitized-observed.jsonl')
    assert [s['path'] for s in CATALOGUE if s['provenance'] == 'observed'] == [
        'pi/sanitized-observed.jsonl']
    assert any(s['path'] == 'captures/turn-evidence-claude.jsonl' for s in CATALOGUE)


def test_session_episodes_matches_catalogue():
    # The existing classifier runs only in a test subprocess with an isolated HOME.
    script = '''import json, runpy, sys
from pathlib import Path
m = runpy.run_path(sys.argv[1], run_name="episodes_test")
out = []
for sample in json.loads(sys.stdin.read()):
    session = m["read_claude" if sample["harness"] == "claude-code" else "read_codex"](Path(sample["path"]))
    kinds = {e.kind for e in session.events}
    out.append("human" if "human" in kinds else "injected" if "injected" in kinds else "other")
print(json.dumps(out))
'''
    root = Path(__file__).resolve().parents[1]
    samples = [dict(harness=s['harness'], path=str(FIXTURES / s['path'])) for s in CORPUS]
    with tempfile.TemporaryDirectory() as home:
        result = subprocess.run([sys.executable, '-c', script, str(root / 'agents/bin/session-episodes')],
                                input=json.dumps(samples), text=True, capture_output=True, check=True,
                                env={'PATH': '/usr/bin:/bin', 'HOME': home, 'USER': 'fixture-user',
                                     'OPENAI_API_KEY': 'fake', 'ANTHROPIC_API_KEY': 'fake'})
    assert json.loads(result.stdout) == [s['expected']['episodes'] for s in CORPUS]


def test_nonhuman_typed_marker_conflicts_even_inside_text(tmp_path):
    path = tmp_path / 'typed-inside.jsonl'
    path.write_text(json.dumps({'type': 'user', 'sessionId': 's', 'origin': {'kind': 'task-notification'},
                              'message': {'content': 'Before <pasted_content>paste</pasted_content>'}}) + '\n')
    place = lines.Place('claude-code', 'file', None, 'explicit', str(path), path)
    record = records.claude_read(place, path.stat().st_size).records[0]
    assert (record['role'], record['rule']) == ('unknown', 'conflict')
    assert record['conflict'] == [{'native_kind': 'task-notification'},
                                  {'markers': [{'name': 'pasted_content', 'lead': 'inside', 'joined': 'inside'}]}]


def test_conflicting_prompt_does_not_relabel_native_tool_result(tmp_path):
    path = tmp_path / 'mixed.jsonl'
    path.write_text(json.dumps({'type': 'user', 'sessionId': 's', 'origin': {'kind': 'human'},
                              'message': {'content': [
                                  {'type': 'text', 'text': '<system-reminder>context</system-reminder>'},
                                  {'type': 'tool_result', 'tool_use_id': 'call', 'content': 'Output'}]}}) + '\n')
    place = lines.Place('claude-code', 'file', None, 'explicit', str(path), path)
    prompt, result = records.claude_read(place, path.stat().st_size).records
    assert (prompt['role'], prompt['rule']) == ('unknown', 'conflict')
    assert (result['role'], result['rule'], result['basis']) == ('tool_output', 'structure', 'native')
    assert 'conflict' not in result


@pytest.mark.parametrize('short,line,want', [
    ('CA', 1, 'native'),
    ('CA', 16, 'native'),
    ('CA', 3, 'native'),
    ('XC', 4, 'convention'),
])
def test_native_and_agent_path_basis(short, line, want):
    sample = next(s for s in CATALOGUE if s['path'] == PATHS[short])
    record = next(r for r in read_sample(sample).records if r['line'] == line)
    assert record['basis'] == want


@pytest.mark.parametrize('short,version', [('CA', '2.1.300'), ('XP', '0.163.0'),
                                          ('CM', '2.1.304'), ('XE', '0.164.0')])
def test_catalogue_preserves_known_synthetic_versions(short, version):
    sample = next(s for s in CATALOGUE if s['path'] == PATHS[short])
    assert (sample['version'], sample['provenance']) == (version, 'synthetic')


@pytest.mark.parametrize('harness', ['claude-code', 'codex'])
@pytest.mark.parametrize('shape,want', [('leading', 'unknown'), ('whitespace', 'unknown'),
                                       ('empty-first', 'unknown'), ('inside', 'user_channel_unattributed')])
def test_unrecognized_wrappers_remain_unknown_only_when_leading(tmp_path, harness, shape, want):
    text = '<future-wrapper>context</future-wrapper>'
    block = 'text' if harness == 'claude-code' else 'input_text'
    content = {'leading': text, 'whitespace': '  ' + text,
               'empty-first': [{'type': block, 'text': ''}, {'type': block, 'text': text}],
               'inside': 'Quoted later: ' + text}[shape]
    if harness == 'claude-code':
        row = {'type': 'user', 'sessionId': 's', 'message': {'content': content}}
    else:
        row = {'type': 'response_item', 'payload': {'type': 'message', 'role': 'user',
                'content': [{'type': block, 'text': content}] if isinstance(content, str) else content}}
    path = tmp_path / 'unknown-wrapper.jsonl'
    path.write_text(json.dumps(row) + '\n')
    place = lines.Place(harness, 'file', None, 'explicit', str(path), path)
    read = records.claude_read(place, path.stat().st_size) if harness == 'claude-code' else records.codex_read(place, path.stat().st_size, lambda _id: None)
    assert read.records
    assert all((r['role'], r['rule'], r['basis'], r['role_basis']) ==
               (want, 'prefix_rule', 'heuristic', 'prefix_rule') for r in read.records)


@pytest.mark.parametrize('native,meta,want,rule', [('human', False, 'human', 'origin'),
                                                 ('task-notification', False, 'injected', 'origin'),
                                                 (None, True, 'injected', 'structure')])
def test_unrecognized_wrapper_does_not_override_native_evidence(tmp_path, native, meta, want, rule):
    row = {'type': 'user', 'sessionId': 's', 'message': {'content': '<future-wrapper>context</future-wrapper>'}}
    if native is not None:
        row['origin'] = {'kind': native}
    if meta:
        row['isMeta'] = True
    path = tmp_path / 'native-wrapper.jsonl'
    path.write_text(json.dumps(row) + '\n')
    place = lines.Place('claude-code', 'file', None, 'explicit', str(path), path)
    record = records.claude_read(place, path.stat().st_size).records[0]
    assert (record['role'], record['rule'], record['basis']) == (want, rule, 'native')
