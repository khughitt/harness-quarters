"""Bounded transition data; no transcript reads, delivery claims or heavy imports."""
from __future__ import annotations

import json
import math
import os

MAX_EVENTS = 128
MAX_BYTES = 131072
SCOPES = {'active': 'tree_active_seconds', 'calls': 'root_attempts',
          'spawns': 'tree_started', 'compactions': 'root'}
REASONS = {'turn_start': {'genuine_user', 'implicit'},
           'warning': {'active', 'calls', 'spawns', 'compactions'},
           'enforced_pause': {'active', 'calls', 'spawns', 'compactions', 'limits-changed'},
           'notification': {None}, 'turn_reset': {'genuine_user'},
           'turn_resume': {'genuine_user'}, 'session_end': {'session_end', 'idle'}}
EVENT_FIELDS = {'version', 'harness', 'root', 'generation', 'turn', 'sequence', 'host',
                'at', 'kind', 'reason', 'snapshot', 'notification', 'source'}


def encode(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def _number(value, name, *, positive=False, integer=False):
    types = (int,) if integer else (int, float)
    if (type(value) not in types or (not integer and not math.isfinite(value))
            or value < 0 or (positive and value == 0)):
        raise ValueError(f'{name} must be a finite {"positive" if positive else "nonnegative"} number')


def validate_snapshot(data):
    if data is None:
        return
    if not isinstance(data, dict) or set(data) != {*SCOPES, 'limits_sha', 'paused', 'counted', 'scopes'}:
        raise ValueError('invalid history snapshot fields')
    if data['scopes'] != SCOPES or not isinstance(data['limits_sha'], str):
        raise ValueError('invalid snapshot scope or limits digest')
    if data['paused'] not in REASONS['enforced_pause'] | {None}:
        raise ValueError('invalid snapshot pause reason')
    counted = data['counted']
    if (not isinstance(counted, dict) or set(counted) != set(SCOPES)
            or any(type(v) is not bool for v in counted.values())
            or not all(counted[n] for n in ('active', 'calls', 'spawns'))):
        raise ValueError('invalid metric countability')
    for name in SCOPES:
        pair = data[name]
        if not isinstance(pair, dict) or set(pair) != {'used', 'limit'}:
            raise ValueError('invalid metric fields')
        _number(pair['limit'], f'{name}.limit', integer=True)
        if counted[name]:
            _number(pair['used'], f'{name}.used', integer=name != 'active')
        elif pair['used'] is not None:
            raise ValueError('uncounted metric must be null')


def validate_event(event):
    if not isinstance(event, dict) or set(event) != EVENT_FIELDS:
        raise ValueError('invalid history event fields')
    if type(event['version']) is not int or event['version'] != 1 or event['source'] != 'hook':
        raise ValueError('unsupported history event version/source')
    for name in ('harness', 'root', 'generation', 'host'):
        if not isinstance(event[name], str) or not event[name] or len(event[name].encode()) > 255:
            raise ValueError(f'invalid history {name}')
    for name in ('turn', 'sequence'):
        _number(event[name], name, positive=True, integer=True)
    _number(event['at'], 'event.at')
    kind = event['kind']
    if not isinstance(kind, str) or kind not in REASONS or event['reason'] not in REASONS[kind]:
        raise ValueError('invalid history kind/reason')
    validate_snapshot(event['snapshot'])
    notice = event['notification']
    if notice is not None:
        if (not isinstance(notice, dict)
                or set(notice) != {'outcome', 'error_code', 'desktop', 'relay', 'receipt', 'pause_sequence'}
                or notice['outcome'] not in {'pending', 'attempted', 'error', 'unknown'}
                or notice['error_code'] not in {None, 'notify_failed'}
                or any(notice[n] != 'unknown' for n in ('desktop', 'relay', 'receipt'))):
            raise ValueError('invalid notification outcome')
        _number(notice['pause_sequence'], 'pause_sequence', positive=True, integer=True)


def snapshot(state, *, compactions_counted: bool) -> dict | None:
    if state is None or state.turn is None:
        return None
    turn = state.turn
    data = {'limits_sha': turn.limits_sha, 'paused': state.paused,
            'counted': {n: n != 'compactions' or compactions_counted for n in SCOPES},
            'scopes': dict(SCOPES)}
    for name in SCOPES:
        data[name] = {'used': (turn.active if name == 'active' else getattr(turn, name))
                      if data['counted'][name] else None,
                      'limit': turn.limits.active_seconds if name == 'active' else getattr(turn.limits, name)}
    return data


def append_event(record, kind: str, now: float, *, reason: str | None,
                 snapshot: dict | None, notification: dict | None = None,
                 turn: int | None = None) -> dict:
    event = dict(version=1, harness=record.harness, root=record.root, generation=record.generation,
                 turn=record.turn_serial if turn is None else turn, sequence=record.event_serial + 1,
                 host=os.uname().nodename, at=now, kind=kind, reason=reason,
                 snapshot=snapshot, notification=notification, source='hook')
    validate_event(event)
    if len(encode([event]).encode()) > MAX_BYTES:
        raise ValueError('individual history event exceeds byte bound')
    record.events.append(event)
    record.event_serial += 1
    while len(record.events) > MAX_EVENTS or len(encode(record.events).encode()) > MAX_BYTES:
        old = record.events.pop(0)
        record.dropped_count += 1
        record.dropped_through = max(record.dropped_through or 0, old['at'])
    return event
