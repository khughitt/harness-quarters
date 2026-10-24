"""Isolated installed-launcher adoption rehearsal; never touches live relay state."""
import contextlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import uuid

def stop(signum, frame):
    raise SystemExit(128 + signum)

signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)

launcher, install_root, old_runtime, evidence = map(Path, sys.argv[1:])
evidence.mkdir(parents=True, exist_ok=True)
home = evidence / 'home'
home.mkdir(exist_ok=True)
state = evidence / 'state'
state.mkdir(mode=0o700, exist_ok=True)
env = {'PATH': os.defpath, 'HOME': str(home), 'RELAY_STATE_DIR': str(state),
       'RELAY_INSTALL_ROOT': str(install_root)}
old = ['/usr/bin/node', str(old_runtime)]
new = [str(launcher)]


def cli(command, *args):
    r = subprocess.run([*command, *args], env=env, text=True, capture_output=True, timeout=15)
    assert r.returncode == 0, (args, r.returncode, r.stdout, r.stderr)
    return json.loads(r.stdout) if '--json' in args else r.stdout.strip()


@contextlib.contextmanager
def service(command, name):
    with (evidence / f'{name}.log').open('w') as log:
        p = subprocess.Popen([*command, 'serve'], env=env, stdin=subprocess.DEVNULL,
                             stdout=log, stderr=subprocess.STDOUT)
        print(f'{name}: pid={p.pid}', flush=True)
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                assert p.poll() is None, f'{name} exited: {p.returncode}'
                try:
                    cli(command, 'presence', '--json')
                    break
                except AssertionError:
                    time.sleep(.05)
            else:
                raise AssertionError(f'{name} did not become ready')
            yield p
        finally:
            p.terminate()
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
            print(f'{name}: reaped pid={p.pid} exit={p.returncode}', flush=True)
            assert p.returncode == 0, f'{name} shutdown failed'


def question(native=None):
    ident = str(uuid.uuid4())
    now = int(time.time() * 1000)
    return {'schema': 1, 'id': ident, 'kind': 'question', 'correlationId': ident,
            'from': {'kind': 'agent', 'agentId': 'codex:isolated-smoke'},
            'to': {'kind': 'user'}, 'createdAt': now,
            'context': {'project': None, 'taskId': None, 'cwd': None},
            'body': {'class': 'clarification', 'expiresAt': now + 3600000,
                     'native': native, 'artifact': None, 'supersedes': None,
                     'items': [{'id': 'q1', 'header': 'Smoke', 'prompt': 'Continue?',
                                'type': 'single', 'options': [
                                    {'id': 'yes', 'label': 'Yes', 'description': None},
                                    {'id': 'no', 'label': 'No', 'description': None}],
                                'recommended': None, 'allowOther': False, 'maxLength': None}]}}


# Preserve a native answer created by the old service across an actual binary upgrade.
q = question({'harness': 'claude-code', 'sessionId': 'isolated', 'callId': 'smoke'})
waiter = {'platform': 'linux', 'host': socket.gethostname(),
          'bootId': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
          'pid': os.getpid(), 'start': Path(f'/proc/{os.getpid()}/stat').read_text().rsplit(')', 1)[1].split()[19]}
with service(old, 'old-service'):
    cli(old, 'presence', 'away', '--json')
    s = socket.socket(socket.AF_UNIX)
    s.settimeout(10)
    s.connect(str(state / 'serve.sock'))
    s.sendall((json.dumps({'reqId': 'legacy', 'op': 'ask', 'message': q,
                          'handback': False, 'waiter': waiter}) + '\n').encode())
    reader = s.makefile('r')
    while True:
        reply = json.loads(reader.readline())
        if reply.get('reqId') == 'legacy':
            assert reply['ok'], reply
            break
    native_answer = cli(old, 'inbox', 'answer', q['id'], 'q1=yes', '--json')['entry']['answer']
reader.close()
s.close()
with service(new, 'upgraded-service'):
    assert cli(new, 'inbox', 'show', q['id'], '--json')['entry']['answer'] == native_answer
    assert cli(new, 'presence', '--json')['presence']['mode'] == 'away'
    print('PASS v0.1.1 saved native answer and presence survive v0.2.0 upgrade', flush=True)
    detached = question()
    file = evidence / 'question.json'
    file.write_text(json.dumps(detached))
    posted = cli(new, 'inbox', 'ask', '--file', str(file), '--json')['entry']
    assert posted['state'] == 'pending' and posted['route']['waiter'] is None
    answered = cli(new, 'inbox', 'answer', detached['id'], 'q1=yes', '--surface', 'terminal', '--json')['entry']
    assert answered['state'] == 'answered'
with service(new, 'restarted-service'):
    saved = cli(new, 'inbox', 'show', detached['id'], '--json')['entry']
    assert saved['answer'] == answered['answer'] and saved['state'] == 'answered'
    first = cli(new, 'inbox', 'take', detached['id'], '--json')['entry']
    assert first['state'] == 'consumed' and first['answer'] == answered['answer']
    assert first['handedAt'] is None
    assert cli(new, 'inbox', 'take', detached['id'], '--json')['entry'] == first
with service(new, 'replay-service'):
    assert cli(new, 'inbox', 'take', detached['id'], '--json')['entry'] == first
    print('PASS ask-file, terminal answer, saved-answer restart, take and replay after restart', flush=True)
assert not (state / 'serve.lock').exists()
print('PASS all services reaped and service lock released', flush=True)
(evidence / 'verdict.json').write_text(json.dumps({'version': cli(new, '--version'),
    'nativeAnswerPreserved': True, 'detachedTakeReplay': True, 'processesReaped': True}, indent=2) + '\n')
