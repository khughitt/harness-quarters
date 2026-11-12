"""Claude filename membership and layout facts preserve the reader's exact conventions."""
import argparse
import json
from pathlib import Path

import pytest

from harness_evidence import discover
from harness_evidence.lines import Place
from test_harness_evidence_stream import invoke, request


def placed(tmp_path, relative, *, store='live'):
    return Place('claude-code', 'claude', 'personal', store, f'projects/{relative}',
                 tmp_path / '.claude/projects' / relative)


@pytest.mark.parametrize('relative,ids', [
    ('p/P.jsonl', ['P']),
    ('p/agent-A.jsonl', ['agent-A']),
    ('p/P/subagents/agent-A.jsonl', ['A', 'P', 'agent-A']),
    ('p/P/subagents/agent-.jsonl', ['P', 'agent-']),
    ('p/P/subagents/agent-agent-A.jsonl', ['P', 'agent-agent-A']),
    ('p/P/subagents/notes.jsonl', []),
    ('p/P/subagents/P.jsonl', []),
    ('p/P/other/agent-A.jsonl', []),
    ('p/P/subagents/deeper/agent-A.jsonl', []),
    ('P.jsonl', []),
    ('a/p/q/P.jsonl', []),
    ('p/[P].jsonl', ['[P]']),
    ('p/P/subagents/agent-A[0].jsonl', ['A[0]', 'P', 'agent-A[0]']),
    ('p/.jsonl', []),
    ('p/agent-.jsonl', ['agent-']),
    ('p/P/subagents/agent-A.jsonl.extra', None),
])
def test_claude_lookup_has_exact_old_membership(tmp_path, relative, ids):
    place = placed(tmp_path, relative)
    observed = discover.filename_lookup('claude-code', place.path, place=place)
    assert observed == (None if ids is None else
                        {'session_ids': ids, 'basis': 'convention', 'rule': 'claude_name_lookup'})


def test_claude_lookup_matches_old_globs_with_query_aliases_and_literal_metacharacters(tmp_path):
    import glob
    root = tmp_path / '.claude/projects'
    names = ['p/P.jsonl', 'p/agent-A.jsonl', 'p/P/subagents/agent-A.jsonl',
             'p/P/subagents/agent-agent-A.jsonl', 'p/P/subagents/agent-[A].jsonl',
             'p/P/subagents/notes.jsonl', 'p/P/subagents/P.jsonl']
    paths = []
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        paths.append(path)
    for query in ('P', 'A', 'agent-A', 'agent-agent-A', '[A]', 'agent-[A]', 'absent'):
        agent = query[len('agent-'):] if query.startswith('agent-') else query
        sid, aid = glob.escape(query), glob.escape(agent)
        # Frozen obs fe61869f _native's three patterns, with its public alias normalization.
        expected = {path for pattern in (f'*/{sid}.jsonl', f'*/{sid}/subagents/agent-*.jsonl',
                                        f'*/*/subagents/agent-{aid}.jsonl') for path in root.glob(pattern)}
        actual = {path for path in paths if query in discover.filename_lookup(
            'claude-code', path, place=placed(tmp_path, path.relative_to(root).as_posix()))['session_ids']}
        assert actual == expected, query


@pytest.mark.parametrize('relative,session,agent,parent,subagent,resume', [
    ('p/P.jsonl', 'P', None, None, False, 'projects/p'),
    ('p/agent-A.jsonl', 'agent-A', 'A', None, False, 'projects/p'),
    ('p/P/subagents/agent-A.jsonl', 'agent-A', 'A', 'P', True, None),
    ('p/P/subagents/notes.jsonl', 'notes', None, 'P', True, None),
    ('deep/p/P/subagents/agent-A.jsonl', 'agent-A', 'A', 'P', True, None),
    ('p/agent-.jsonl', 'agent-', '', None, False, 'projects/p'),
    ('p/P/subagents/agent-A.other', 'agent-A', 'A', 'P', True, None),
])
def test_path_facts_are_logical_claims_at_any_indexed_depth(tmp_path, relative, session, agent, parent, subagent, resume):
    place = placed(tmp_path, relative)
    assert callable(getattr(discover, 'path_facts', None)), 'normalized path facts exporter is absent'
    assert discover.path_facts(place) == {
        'session': session, 'agent': agent, 'parent': parent, 'subagent': subagent,
        'resume_group': resume, 'basis': 'convention', 'rule': 'claude_path_layout',
        'ref': f'claude:projects/{relative}'}
    assert not place.path.exists()


def test_explicit_and_other_harness_paths_do_not_claim_store_lookup(tmp_path):
    place = placed(tmp_path, 'p/P.jsonl', store='explicit')
    assert discover.filename_lookup('claude-code', place.path, place=place) is None
    assert discover.filename_lookup('claude-code', place.path) is None
    assert callable(getattr(discover, 'path_facts', None)), 'normalized path facts exporter is absent'
    for harness in ('codex', 'unknown'):
        assert discover.path_facts(Place(harness, 'file', None, 'explicit', 'x', tmp_path / 'x')) is None


def test_discovery_path_facts_cover_alias_names_without_opening_bytes(tmp_path, monkeypatch, capsys):
    from harness_evidence.__main__ import _discover
    root = tmp_path / '.claude/projects'
    main = root / 'p/P.jsonl'
    main.parent.mkdir(parents=True)
    main.write_bytes(b'not transcript data\n')
    child = root / 'p/P/subagents/agent-A.jsonl'
    child.parent.mkdir(parents=True)
    child.symlink_to(main)
    dangling = child.with_name('agent-B.jsonl')
    dangling.symlink_to(child.parent / 'absent.jsonl')
    def forbidden(*args, **kwargs):
        raise AssertionError('filename discovery must never open transcript bytes')
    monkeypatch.setattr(Path, 'open', forbidden)
    _discover(argparse.Namespace(home=None, root=[('claude-code', root)]), {})
    output = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert output[-1] == {'object': 'discover_end', 'roots': 1, 'files': 1}
    assert output[1]['filename_lookup']['session_ids'] == ['P']
    assert output[1]['path_facts']['resume_group'] == 'projects/p'
    assert [(Path(alias['path']).name, alias['filename_lookup']['session_ids'], alias['path_facts']['agent'])
            for alias in output[0]['aliases']] == [
                ('agent-A.jsonl', ['A', 'P', 'agent-A'], 'A'),
                ('agent-B.jsonl', ['B', 'P', 'agent-B'], 'B')]


def test_file_start_names_logical_replay_and_vanished_paths(tmp_path):
    logical = tmp_path / '.claude/projects/p/P/subagents/agent-A.jsonl'
    physical = tmp_path / 'external/mirror.data'
    physical.parent.mkdir()
    physical.write_text(json.dumps({'type': 'user', 'sessionId': 'P', 'agentId': 'B',
                                    'message': {'content': 'hello'}}) + '\n')
    root = tmp_path / '.claude/projects'
    files = [{'path': str(logical), 'read_path': str(physical), 'size': physical.stat().st_size}]
    output = invoke(tmp_path, request(files, roots=[{'harness': 'claude-code', 'path': str(root)}]))
    fact = output[0]['path_facts']
    assert fact == {'session': 'agent-A', 'agent': 'A', 'parent': 'P', 'subagent': True,
                    'resume_group': None, 'basis': 'convention', 'rule': 'claude_path_layout',
                    'ref': 'claude:projects/p/P/subagents/agent-A.jsonl'}
    header = next(row['header'] for row in output if row['object'] == 'session')
    assert header['agent'] == 'B'
    missing = invoke(tmp_path, request([{'path': str(logical), 'size': 0}],
                                      roots=[{'harness': 'claude-code', 'path': str(root)}]))
    assert missing[0]['path_facts'] == fact
    assert missing[-2]['status'] == 'vanished'
