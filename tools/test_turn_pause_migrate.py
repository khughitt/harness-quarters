"""Explicit offline state conversion never activates or mutates its source."""
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from turn_pause.state import Store

FIXTURE = Path(__file__).parent / 'fixtures/turn-pause/history/legacy-active.json'
ENTRY = Path(__file__).parent / 'turn-pause-migrate'


def source(tmp_path):
    root = tmp_path / 'source'
    root.mkdir(mode=0o700)
    raw = FIXTURE.read_bytes()
    (root / 'codex-r1.json').write_bytes(raw)
    (root / 'codex-r1.lock').touch(mode=0o600)
    return root, raw


def convert(*args, **kwargs):
    return importlib.import_module('turn_pause.migrate').convert(*args, **kwargs)


def test_offline_conversion_preserves_all_active_fields_and_source(tmp_path):
    src, raw = source(tmp_path)
    dst = tmp_path / 'converted'
    result = convert(str(src), str(dst), to_version=1, now=100)
    assert result['complete'] and result['from_version'] == 0 and result['to_version'] == 1
    assert (src / 'codex-r1.json').read_bytes() == raw
    assert [p.name for p in dst.iterdir()] == ['codex-r1.json']
    data = json.loads((dst / 'codex-r1.json').read_bytes())
    assert data['state'] == json.loads(raw)
    assert data['events'] == [] and data['created_at'] == 100
    assert Store(dst).read('codex', 'r1').turn.spawns == 31
    assert result['files'][0]['input_sha256'] and result['files'][0]['output_sha256']


def test_rollback_export_uses_current_state_and_keeps_history_source(tmp_path):
    src, _ = source(tmp_path)
    dst = tmp_path / 'converted'
    assert convert(str(src), str(dst), to_version=1, now=100)['complete']
    with Store(dst).locked('codex', 'r1') as record:
        record.state.turn.calls = 444
    before = (dst / 'codex-r1.json').read_bytes()
    out = tmp_path / 'export'
    result = convert(str(dst), str(out), to_version=0, now=101)
    assert result['complete'] and json.loads((out / 'codex-r1.json').read_bytes())['turn']['calls'] == 444
    assert (dst / 'codex-r1.json').read_bytes() == before


@pytest.mark.parametrize('kind', ['existing', 'overlap', 'symlink', 'unexpected', 'mixed'])
def test_migration_refuses_unsafe_inputs_without_overwrite(tmp_path, kind):
    src, raw = source(tmp_path)
    dst = tmp_path / 'converted'
    if kind == 'existing':
        dst.mkdir()
    elif kind == 'overlap':
        dst = src / 'converted'
    elif kind == 'symlink':
        (src / 'codex-other.json').symlink_to(src / 'codex-r1.json')
    elif kind == 'unexpected':
        (src / 'receipt.json').write_text('{}')
    else:
        (src / 'codex-other.json').write_text('{"version":1}')
    result = convert(str(src), str(dst), to_version=1, now=100)
    assert not result['complete'] and result['errors']
    assert (src / 'codex-r1.json').read_bytes() == raw


def test_partial_conversion_is_identified_and_cannot_be_overwritten(tmp_path, monkeypatch):
    src, raw = source(tmp_path)
    (src / 'codex-r2.json').write_bytes(raw.replace(b'"r1"', b'"r2"'))
    dst = tmp_path / 'converted'
    real = os.replace
    count = 0

    def fail_second(a, b):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError('synthetic write failure')
        real(a, b)

    monkeypatch.setattr(os, 'replace', fail_second)
    result = convert(str(src), str(dst), to_version=1, now=100)
    assert not result['complete'] and len(result['files']) == 1
    assert not convert(str(src), str(dst), to_version=1, now=101)['complete']
    assert (src / 'codex-r1.json').read_bytes() == raw


def test_migration_cli_emits_receipt_only_to_stdout(tmp_path):
    src, _ = source(tmp_path)
    home = tmp_path / 'home'
    home.mkdir()
    env = {'PATH': '/usr/bin:/bin', 'HOME': str(home)}
    dst = tmp_path / 'converted'
    run = subprocess.run([sys.executable, str(ENTRY), '--source', str(src), '--destination', str(dst),
                          '--to-version', '1'], env=env, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)['complete']
    assert not (dst / 'receipt.json').exists()
