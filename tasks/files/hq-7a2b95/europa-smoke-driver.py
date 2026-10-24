import hashlib,json,os,signal,subprocess,tempfile
from pathlib import Path
home=Path.home()
root=Path(subprocess.check_output(['tasks','root','hq-536849','--pretty'],text=True).strip())
expected={'justfile': 'a09af3f5a943b9cf26b45f110dcd06858e2add49658f91719bb6ba4953128206', 'relay/package.json': '20804b02ce2e78ca4fb390676e9646ccd93ff312eabb3c2286ccd0b1ce7134ba', 'relay/package-lock.json': '897d2cd580246fe86b16e4992ee617be99d0e70ae916e4fd01555116164eeab2', 'relay/bin/relay': 'ab73d095374a6a04960897485f29d337c95ac792eb02ffa836b3fbefd83709f9'}
for name,want in expected.items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==want,name
launcher=home/'.local/bin/relay'
assert launcher.resolve()==root/'relay/bin/relay'
lock=json.loads((home/'.local/share/relay/v0.2.0/package-lock.json').read_text())
commit='067c63921602e694682d47bdb2412862359c75ff'
assert lock['packages']['node_modules/relay']['resolved'].endswith('#'+commit)
def out(argv,env):
    r=subprocess.run(argv,env=env,capture_output=True,text=True,timeout=15)
    assert r.returncode==0,(argv,r.stdout,r.stderr)
    return r.stdout.strip()
version=out([str(launcher),'--version'],{'PATH':os.defpath,'HOME':str(home)})
assert version=='relay 0.2.0',version
state=out(['systemctl','--user','show','relay-serve.service','-p','LoadState','-p','ActiveState'],dict(PATH=os.defpath,HOME=str(home),XDG_RUNTIME_DIR='/run/user/'+str(os.getuid())))
assert 'LoadState=not-found' in state,state
active=[]
for file in Path('/proc').glob('[0-9]*/cmdline'):
    try:argv=file.read_bytes().decode().split('\0')
    except (OSError,UnicodeError):continue
    if 'serve' in argv and any(a.endswith('/relay/bin/relay.js') for a in argv):active.append(file.parent.name)
assert not active,active
child=None
def stop(signum,frame):
    if child and child.poll() is None:
        child.terminate()
        try:child.wait(timeout=15)
        except subprocess.TimeoutExpired:child.kill();child.wait()
    raise SystemExit(128+signum)
for signum in [signal.SIGINT,signal.SIGTERM,signal.SIGHUP]:signal.signal(signum,stop)
with tempfile.TemporaryDirectory(prefix='relay-europa-smoke-') as directory:
    temporary=Path(directory)
    script=temporary/'runtime-smoke.py'
    script.write_text('"""Isolated installed-launcher adoption rehearsal; never touches live relay state."""\nimport contextlib\nimport json\nimport os\nfrom pathlib import Path\nimport signal\nimport socket\nimport subprocess\nimport sys\nimport time\nimport uuid\n\ndef stop(signum, frame):\n    raise SystemExit(128 + signum)\n\nsignal.signal(signal.SIGTERM, stop)\nsignal.signal(signal.SIGINT, stop)\n\nlauncher, install_root, old_runtime, evidence = map(Path, sys.argv[1:])\nevidence.mkdir(parents=True, exist_ok=True)\nhome = evidence / \'home\'\nhome.mkdir(exist_ok=True)\nstate = evidence / \'state\'\nstate.mkdir(mode=0o700, exist_ok=True)\nenv = {\'PATH\': os.defpath, \'HOME\': str(home), \'RELAY_STATE_DIR\': str(state),\n       \'RELAY_INSTALL_ROOT\': str(install_root)}\nold = [\'/usr/bin/node\', str(old_runtime)]\nnew = [str(launcher)]\n\n\ndef cli(command, *args):\n    r = subprocess.run([*command, *args], env=env, text=True, capture_output=True, timeout=15)\n    assert r.returncode == 0, (args, r.returncode, r.stdout, r.stderr)\n    return json.loads(r.stdout) if \'--json\' in args else r.stdout.strip()\n\n\n@contextlib.contextmanager\ndef service(command, name):\n    with (evidence / f\'{name}.log\').open(\'w\') as log:\n        p = subprocess.Popen([*command, \'serve\'], env=env, stdin=subprocess.DEVNULL,\n                             stdout=log, stderr=subprocess.STDOUT)\n        print(f\'{name}: pid={p.pid}\', flush=True)\n        try:\n            deadline = time.monotonic() + 10\n            while time.monotonic() < deadline:\n                assert p.poll() is None, f\'{name} exited: {p.returncode}\'\n                try:\n                    cli(command, \'presence\', \'--json\')\n                    break\n                except AssertionError:\n                    time.sleep(.05)\n            else:\n                raise AssertionError(f\'{name} did not become ready\')\n            yield p\n        finally:\n            p.terminate()\n            try:\n                p.wait(timeout=10)\n            except subprocess.TimeoutExpired:\n                p.kill()\n                p.wait()\n            print(f\'{name}: reaped pid={p.pid} exit={p.returncode}\', flush=True)\n            assert p.returncode == 0, f\'{name} shutdown failed\'\n\n\ndef question(native=None):\n    ident = str(uuid.uuid4())\n    now = int(time.time() * 1000)\n    return {\'schema\': 1, \'id\': ident, \'kind\': \'question\', \'correlationId\': ident,\n            \'from\': {\'kind\': \'agent\', \'agentId\': \'codex:isolated-smoke\'},\n            \'to\': {\'kind\': \'user\'}, \'createdAt\': now,\n            \'context\': {\'project\': None, \'taskId\': None, \'cwd\': None},\n            \'body\': {\'class\': \'clarification\', \'expiresAt\': now + 3600000,\n                     \'native\': native, \'artifact\': None, \'supersedes\': None,\n                     \'items\': [{\'id\': \'q1\', \'header\': \'Smoke\', \'prompt\': \'Continue?\',\n                                \'type\': \'single\', \'options\': [\n                                    {\'id\': \'yes\', \'label\': \'Yes\', \'description\': None},\n                                    {\'id\': \'no\', \'label\': \'No\', \'description\': None}],\n                                \'recommended\': None, \'allowOther\': False, \'maxLength\': None}]}}\n\n\n# Preserve a native answer created by the old service across an actual binary upgrade.\nq = question({\'harness\': \'claude-code\', \'sessionId\': \'isolated\', \'callId\': \'smoke\'})\nwaiter = {\'platform\': \'linux\', \'host\': socket.gethostname(),\n          \'bootId\': Path(\'/proc/sys/kernel/random/boot_id\').read_text().strip(),\n          \'pid\': os.getpid(), \'start\': Path(f\'/proc/{os.getpid()}/stat\').read_text().rsplit(\')\', 1)[1].split()[19]}\nwith service(old, \'old-service\'):\n    cli(old, \'presence\', \'away\', \'--json\')\n    s = socket.socket(socket.AF_UNIX)\n    s.settimeout(10)\n    s.connect(str(state / \'serve.sock\'))\n    s.sendall((json.dumps({\'reqId\': \'legacy\', \'op\': \'ask\', \'message\': q,\n                          \'handback\': False, \'waiter\': waiter}) + \'\\n\').encode())\n    reader = s.makefile(\'r\')\n    while True:\n        reply = json.loads(reader.readline())\n        if reply.get(\'reqId\') == \'legacy\':\n            assert reply[\'ok\'], reply\n            break\n    native_answer = cli(old, \'inbox\', \'answer\', q[\'id\'], \'q1=yes\', \'--json\')[\'entry\'][\'answer\']\nreader.close()\ns.close()\nwith service(new, \'upgraded-service\'):\n    assert cli(new, \'inbox\', \'show\', q[\'id\'], \'--json\')[\'entry\'][\'answer\'] == native_answer\n    assert cli(new, \'presence\', \'--json\')[\'presence\'][\'mode\'] == \'away\'\n    print(\'PASS v0.1.1 saved native answer and presence survive v0.2.0 upgrade\', flush=True)\n    detached = question()\n    file = evidence / \'question.json\'\n    file.write_text(json.dumps(detached))\n    posted = cli(new, \'inbox\', \'ask\', \'--file\', str(file), \'--json\')[\'entry\']\n    assert posted[\'state\'] == \'pending\' and posted[\'route\'][\'waiter\'] is None\n    answered = cli(new, \'inbox\', \'answer\', detached[\'id\'], \'q1=yes\', \'--surface\', \'terminal\', \'--json\')[\'entry\']\n    assert answered[\'state\'] == \'answered\'\nwith service(new, \'restarted-service\'):\n    saved = cli(new, \'inbox\', \'show\', detached[\'id\'], \'--json\')[\'entry\']\n    assert saved[\'answer\'] == answered[\'answer\'] and saved[\'state\'] == \'answered\'\n    first = cli(new, \'inbox\', \'take\', detached[\'id\'], \'--json\')[\'entry\']\n    assert first[\'state\'] == \'consumed\' and first[\'answer\'] == answered[\'answer\']\n    assert first[\'handedAt\'] is None\n    assert cli(new, \'inbox\', \'take\', detached[\'id\'], \'--json\')[\'entry\'] == first\nwith service(new, \'replay-service\'):\n    assert cli(new, \'inbox\', \'take\', detached[\'id\'], \'--json\')[\'entry\'] == first\n    print(\'PASS ask-file, terminal answer, saved-answer restart, take and replay after restart\', flush=True)\nassert not (state / \'serve.lock\').exists()\nprint(\'PASS all services reaped and service lock released\', flush=True)\n(evidence / \'verdict.json\').write_text(json.dumps({\'version\': cli(new, \'--version\'),\n    \'nativeAnswerPreserved\': True, \'detachedTakeReplay\': True, \'processesReaped\': True}, indent=2) + \'\\n\')\n')
    driver_home=temporary/'driver-home';driver_home.mkdir()
    child=subprocess.Popen(['/usr/bin/python3',str(script),str(launcher),str(home/'.local/share/relay'),str(home/'.local/share/relay/v0.1.1/node_modules/relay/bin/relay.js'),str(temporary/'evidence')],env={'PATH':os.defpath,'HOME':str(driver_home)},stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:stdout,stderr=child.communicate(timeout=90)
    except BaseException:
        child.terminate()
        try:child.wait(timeout=15)
        except subprocess.TimeoutExpired:child.kill();child.wait()
        raise
    assert child.returncode==0,(child.returncode,stdout,stderr)
    verdict=json.loads((temporary/'evidence/verdict.json').read_text())
report={'host':'europa','version':version,'releaseCommit':commit,'inputHashes':expected,'serviceConfigured':False,'smokeLog':stdout,'smokeVerdict':verdict,'temporaryStateRemoved':not temporary.exists(),'installedRuntime':'$HOME/.local/share/relay/v0.2.0/node_modules/relay/bin/relay.js'}
print(json.dumps(report,indent=2))
