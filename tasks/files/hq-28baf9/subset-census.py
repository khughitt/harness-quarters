"""Counts-only census of Claude resume pairs using the shipped reader's predicates.

Reads each native Claude main file at its size on open; never writes session stores.
Keeps UUIDs, timed-line metadata and native continued-in links, never transcript text.
Run self-checks and one live project (--pilot) before the complete two-root census.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time


def compact(read, sessions, FileRead):
    timed = sessions._timed_turns(read)
    records = {}
    for record in read.records:
        if record['line'] in timed or '_continued_in' in record:
            records.setdefault(record['line'], {k: record[k] for k in
                ('line', 'kind', 'at', '_continued_in', 'copy') if k in record})
    return FileRead(read.place, list(records.values()), [],
                    {k: read.header.get(k) for k in ('session', 'uuids', 'subagent')})


def count_pairs(reads, sessions):
    counts, inverse, pairs = Counter(), defaultdict(list), set()
    for i, read in enumerate(reads):
        for uuid in read.header['uuids']:
            for j in inverse[uuid]:
                pairs.add((j, i))
            inverse[uuid].append(i)
    for i, j in sorted(pairs):
        a, b = reads[i], reads[j]
        au, bu = a.header['uuids'], b.header['uuids']
        shared = set(au) & set(bu)
        counts['shared_uuid_pairs'] += 1
        at, bt = sessions._timed_turns(a), sessions._timed_turns(b)
        ax, bx = set(at) - {au[u] for u in shared}, set(bt) - {bu[u] for u in shared}
        linked = sessions._named(a, b) != sessions._named(b, a)
        if bool(ax) != bool(bx):
            counts['one_sided_no_unshared_timed_pairs'] += 1
            counts['one_sided_native_link' if linked else 'one_sided_no_native_link'] += 1
            direction = sessions._direction(a, b, shared)
            if direction is None:
                counts['one_sided_tie'] += 1
            else:
                active = a if ax else b
                counts['one_sided_copy_is_side_with_unshared_timed' if direction[0] is active
                       else 'one_sided_copy_is_side_without_unshared_timed'] += 1
        if set(au) < set(bu) or set(bu) < set(au):
            counts['strict_uuid_subset_pairs'] += 1
            counts['strict_subset_native_link' if linked else 'strict_subset_no_native_link'] += 1
        if not ax and not bx:
            counts['neither_side_has_unshared_timed'] += 1
    return counts


def self_check(sessions, FileRead, Place):
    def read(name, extra=False):
        place = Place('claude-code', 'fixture', 'personal', 'live', name, Path(name))
        records = [{'line': n, 'kind': 'user', 'at': f'2026-10-01T00:00:0{n}Z'}
                   for n in range(1, 4 + extra)]
        return FileRead(place, records, [], {'session': name,
            'uuids': {f'r{n}': n for n in range(1, 4 + extra)}, 'subagent': False})
    a, b = read('A'), read('B', True)
    shared = {'r1', 'r2', 'r3'}
    assert sessions._direction(a, b, shared) == (b, a)  # completed-resume interpretation
    a, b = read('A', True), read('B')
    assert sessions._direction(a, b, shared) == (a, b)  # abandoned-copy reverse case
    got = count_pairs([a, b], sessions)
    assert got['strict_subset_no_native_link'] == 1
    assert got['one_sided_copy_is_side_with_unshared_timed'] == 1
    a.records.append({'line': 5, 'kind': 'continued-in', '_continued_in': 'B'})
    assert sessions._direction(a, b, shared) == (b, a)  # native link overrides timing
    assert count_pairs([a, b], sessions)['one_sided_native_link'] == 1
    assert sessions._direction(read('A'), read('B'), shared) is None
    assert count_pairs([read('A'), read('B')], sessions)['neither_side_has_unshared_timed'] == 1
    return {'completed_resume': 'pass', 'reverse_case': 'pass', 'native_link': 'pass',
            'identical_tie': 'pass', 'counter_categories': 'pass'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--obs', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--pilot', action='store_true')
    args = parser.parse_args()
    sys.path.insert(0, str(args.obs))
    import session_logs_place as place
    import session_logs_sessions as sessions
    from session_logs_records import FileRead, claude_read
    from session_logs_lines import Place
    started = time.monotonic()
    checks = self_check(sessions, FileRead, Place)
    env = {'HOME': os.environ['HOME']}
    if os.environ.get('OBS_CLAUDE_PROJECTS'):
        env['OBS_CLAUDE_PROJECTS'] = os.environ['OBS_CLAUDE_PROJECTS']
    roots = [root for root in place.roots(env) if root.harness == 'claude-code']
    listing = place.list_files(roots, None)
    grouped = defaultdict(list)
    for path in listing.files:
        if path.parent.name != 'subagents':
            grouped[path.parent].append(path)
    groups = sorted(grouped.items(), key=lambda item: str(item[0]))
    if args.pilot:
        eligible = [(directory, paths) for directory, paths in groups if len(paths) >= 2]
        if not eligible:
            raise ValueError('no live project with two main files for the pilot')
        groups = [min(eligible, key=lambda item: sum(path.stat().st_size for path in item[1]))]
    per_root = defaultdict(Counter)
    for directory, paths in groups:
        reads = []
        owner = next(root for root in roots if directory.is_relative_to(root.path))
        stats = per_root[owner.home]
        stats['projects'] += 1
        for path in sorted(paths):
            before = path.stat()
            stats['files'] += 1
            stats['bytes_at_open'] += before.st_size
            read = claude_read(place.place_of(path, roots), before.st_size)
            stats['unparsed_lines'] += len(read.unparsed)
            if path.stat().st_size != before.st_size:
                stats['size_changed_during_read'] += 1
            if read.header.get('subagent'):
                stats['sidechain_main_files_excluded'] += 1
                continue
            if not read.header.get('session'):
                stats['identityless_files_excluded'] += 1
                continue
            stats['main_files_compared'] += 1
            reads.append(compact(read, sessions, FileRead))
            del read
        stats.update(count_pairs(reads, sessions))
    totals = Counter()
    for stats in per_root.values():
        totals.update(stats)
    out = {'scope': 'one_live_project_pilot' if args.pilot else 'all_native_claude_main_files',
           'self_checks': checks, 'root_states': listing.roots,
           'aliases_not_read': len(listing.aliases), 'per_root': dict(per_root),
           'totals': dict(totals), 'elapsed_s': round(time.monotonic() - started, 2),
           'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
           'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           'reader_source_sha256': {name: hashlib.sha256((args.obs / name).read_bytes()).hexdigest()
               for name in ('session_logs_sessions.py', 'session_logs_records.py')},
           'verdict': 'complete',
           'limits': ['Only current native regular main files within each Claude project directory',
                      'Symlink aliases, archived/pruned files and subagent files excluded',
                      'Each file bounded at size on open; this is not a simultaneous snapshot',
                      'Pair shapes do not establish which session was actually opened first']}
    if any(root['state'] == 'unreadable' for root in listing.roots):
        out['verdict'] = 'incomplete_unreadable_root'
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'scope': out['scope'], 'verdict': out['verdict'], 'totals': dict(totals),
                      'elapsed_s': out['elapsed_s'], 'self_checks': checks}))
    return 0 if out['verdict'] == 'complete' else 1


if __name__ == '__main__':
    raise SystemExit(main())
