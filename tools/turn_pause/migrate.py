"""Explicit offline conversion; never selected by the hook's runtime reader."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

from .state import (StateError, Store, new_record, parse_json, parse_record,
                    record_json, state_dict, state_from_dict, write_atomic)


def convert(source: str, destination: str, *, to_version: int, now: float) -> dict:
    receipt = {'version': 1, 'from_version': 0 if to_version == 1 else 1,
               'to_version': to_version, 'complete': False, 'files': [],
               'skipped_ended': [], 'errors': [], 'destination': destination}
    try:
        if type(to_version) is not int or to_version not in (0, 1):
            raise ValueError('to_version must be 0 or 1')
        src, dst = Path(source), Path(destination)
        if src.is_symlink() or not src.is_dir():
            raise ValueError('source must be a real directory')
        src_real, dst_real = src.resolve(), dst.resolve()
        if src_real == dst_real or src_real in dst_real.parents or dst_real in src_real.parents:
            raise ValueError('source and destination must not overlap')
        if dst.exists() or dst.is_symlink():
            raise ValueError('destination must not exist; preserve or dispose of prior staging explicitly')
        prepared = []
        for path in sorted(src.iterdir()):
            if path.is_symlink() or not path.is_file():
                raise ValueError('source contains a nonregular input')
            if path.name.endswith('.lock'):
                continue
            if path.name.startswith('.') or not path.name.endswith('.json'):
                raise ValueError('source contains an unexpected input')
            raw = path.read_bytes()
            if to_version == 1:
                state = state_from_dict(parse_json(raw.decode()))
                record = new_record(state.harness, state.root, now)
                record.state = state
                record.turn_serial = 1 if state.turn is not None else 0
                encoded = record_json(record).encode()
            else:
                record = parse_record(raw.decode())
                if record.state is None:
                    receipt['skipped_ended'].append(path.name)
                    state = None
                    encoded = None
                else:
                    state = record.state
                    encoded = json.dumps(state_dict(state), separators=(',', ':'), allow_nan=False).encode()
            if path.name != Store(str(src))._stem(record.harness, record.root) + '.json':
                raise ValueError('source filename and identity differ')
            prepared.append((path.name, raw, encoded))
        dst.mkdir(mode=0o700)
        for name, raw, encoded in prepared:
            if encoded is None:
                continue
            write_atomic(str(dst / name), encoded)
            receipt['files'].append({'name': name, 'input_sha256': hashlib.sha256(raw).hexdigest(),
                                     'output_sha256': hashlib.sha256(encoded).hexdigest()})
        receipt['complete'] = True
    except (OSError, ValueError, TypeError, KeyError, StateError) as error:
        # The receipt identifies the failed stage without copying state or credentials.
        receipt['errors'].append(type(error).__name__)
    return receipt


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Offline pause-state conversion; source stays unchanged.')
    parser.add_argument('--source', required=True)
    parser.add_argument('--destination', required=True)
    parser.add_argument('--to-version', type=int, choices=(0, 1), required=True)
    args = parser.parse_args(argv)
    receipt = convert(args.source, args.destination, to_version=args.to_version, now=time.time())
    print(json.dumps(receipt))
    return 0 if receipt['complete'] else 1
