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
EVENT_FIELDS = frozenset({'version', 'harness', 'root', 'generation', 'turn', 'sequence', 'host',
                          'at', 'kind', 'reason', 'snapshot', 'notification', 'source'})
SNAP_FIELDS = frozenset({*SCOPES, 'limits_sha', 'paused', 'counted', 'scopes'})
PAUSE_REASONS = frozenset(REASONS['enforced_pause'] | {None})
SCOPE_KEYS = frozenset(SCOPES)
PAIR_KEYS = frozenset({'used', 'limit'})
NOTICE_KEYS = frozenset({'outcome', 'error_code', 'desktop', 'relay', 'receipt', 'pause_sequence'})
OUTCOMES = frozenset({'pending', 'attempted', 'error', 'unknown'})
ERROR_CODES = frozenset({None, 'notify_failed'})
_ENCODE = json.JSONEncoder(ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode
_HOST = os.uname().nodename


def encode(value) -> str:
    return _ENCODE(value)


def _number(value, name, *, positive=False, integer=False):
    t = type(value)
    if integer:
        if t is not int or value < 0 or (positive and value == 0):
            raise ValueError(f'{name} must be a finite {"positive" if positive else "nonnegative"} number')
    elif t not in (int, float) or not math.isfinite(value) or value < 0 or (positive and value == 0):
        raise ValueError(f'{name} must be a finite {"positive" if positive else "nonnegative"} number')


def validate_snapshot(data):
    if data is None:
        return
    if type(data) is not dict or len(data) != 8 or data.keys() != SNAP_FIELDS:
        raise ValueError('invalid history snapshot fields')
    if data['scopes'] != SCOPES or type(data['limits_sha']) is not str:
        raise ValueError('invalid snapshot scope or limits digest')
    if data['paused'] not in PAUSE_REASONS:
        raise ValueError('invalid snapshot pause reason')
    counted = data['counted']
    if (type(counted) is not dict or len(counted) != 4 or counted.keys() != SCOPE_KEYS
            or type(counted['active']) is not bool or type(counted['calls']) is not bool
            or type(counted['spawns']) is not bool or type(counted['compactions']) is not bool
            or not (counted['active'] and counted['calls'] and counted['spawns'])):
        raise ValueError('invalid metric countability')
    for name in ('active', 'calls', 'spawns', 'compactions'):
        pair = data[name]
        if type(pair) is not dict or len(pair) != 2 or pair.keys() != PAIR_KEYS:
            raise ValueError('invalid metric fields')
        _number(pair['limit'], f'{name}.limit', integer=True)
        if counted[name]:
            _number(pair['used'], f'{name}.used', integer=name != 'active')
        elif pair['used'] is not None:
            raise ValueError('uncounted metric must be null')


def validate_event(event):
    if type(event) is not dict or len(event) != 13 or event.keys() != EVENT_FIELDS:
        raise ValueError('invalid history event fields')
    if type(event['version']) is not int or event['version'] != 1 or event['source'] != 'hook':
        raise ValueError('unsupported history event version/source')
    for name in ('harness', 'root', 'generation', 'host'):
        val = event[name]
        if type(val) is not str or not val or (len(val) > 63 and len(val.encode()) > 255):
            raise ValueError(f'invalid history {name}')
    _number(event['turn'], 'turn', positive=True, integer=True)
    _number(event['sequence'], 'sequence', positive=True, integer=True)
    _number(event['at'], 'event.at')
    kind = event['kind']
    if type(kind) is not str or kind not in REASONS or event['reason'] not in REASONS[kind]:
        raise ValueError('invalid history kind/reason')
    validate_snapshot(event['snapshot'])
    notice = event['notification']
    if notice is not None:
        if (type(notice) is not dict or len(notice) != 6 or notice.keys() != NOTICE_KEYS
                or notice['outcome'] not in OUTCOMES
                or notice['error_code'] not in ERROR_CODES
                or notice['desktop'] != 'unknown' or notice['relay'] != 'unknown' or notice['receipt'] != 'unknown'):
            raise ValueError('invalid notification outcome')
        _number(notice['pause_sequence'], 'pause_sequence', positive=True, integer=True)


def snapshot(state, *, compactions_counted: bool) -> dict | None:
    if state is None or state.turn is None:
        return None
    turn = state.turn
    limits = turn.limits
    return {
        'limits_sha': turn.limits_sha,
        'paused': state.paused,
        'counted': {'active': True, 'calls': True, 'spawns': True, 'compactions': bool(compactions_counted)},
        'scopes': dict(SCOPES),
        'active': {'used': turn.active, 'limit': limits.active_seconds},
        'calls': {'used': turn.calls, 'limit': limits.calls},
        'spawns': {'used': turn.spawns, 'limit': limits.spawns},
        'compactions': {'used': turn.compactions if compactions_counted else None, 'limit': limits.compactions},
    }


def append_event(record, kind: str, now: float, *, reason: str | None,
                 snapshot: dict | None, notification: dict | None = None,
                 turn: int | None = None) -> dict:
    event = dict(version=1, harness=record.harness, root=record.root, generation=record.generation,
                 turn=record.turn_serial if turn is None else turn, sequence=record.event_serial + 1,
                 host=_HOST, at=now, kind=kind, reason=reason,
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


def start_turn(record, now: float, *, origin: str, before: dict | None, after: dict) -> None:
    if origin == 'genuine_user' and record.turn_serial:
        resumed = record.ended_at is not None or (before is not None and before['paused'] is not None)
        append_event(record, 'turn_resume' if resumed else 'turn_reset', now,
                     reason='genuine_user', snapshot=before)
    record.turn_serial += 1
    append_event(record, 'turn_start', now, reason=origin, snapshot=after)
