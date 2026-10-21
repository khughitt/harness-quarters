"""Cutover checks and recovery run against disposable homes, files and repositories."""
import copy
import importlib.machinery
import importlib.util
import json
import os
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "relay-cutover"
GUARD = {"matcher": "Bash", "hooks": [
    {"type": "command", "command": "~/d/ops/hooks/claude-pretooluse"},
]}
# Representative groups copied from the native settings, before the relay cutover.
CLAUDE = {
    "model": "keep-this-pick",
    "hooks": {
        "SessionStart": [{"hooks": [
            {"type": "command", "command": "~/d/familiar/bin/familiar hook SessionStart"},
        ]}],
        "PreToolUse": [
            {"matcher": "*", "hooks": [
                {"type": "command", "command": "~/d/familiar/bin/familiar hook PreToolUse"},
            ]},
            GUARD,
        ],
        "Stop": [{"hooks": [
            {"type": "command", "command": "~/d/ops/hooks/claim-guard"},
        ]}],
    },
    "statusLine": {"type": "command", "command": "~/d/familiar/bin/familiar statusline"},
}
CODEX = {"hooks": {
    "SessionStart": [{"hooks": [
        {"type": "command", "command": "~/d/familiar/bin/familiar hook --agent codex SessionStart"},
    ]}],
    "PreToolUse": [{"matcher": "*", "hooks": [
        {"type": "command", "command": "~/d/familiar/bin/familiar hook --agent codex PreToolUse"},
    ]}],
    "Stop": [{"hooks": [
        {"type": "command", "command": "~/d/ops/hooks/claim-guard --harness codex"},
    ]}],
}}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


class Sandbox:
    def __init__(self, tmp, monkeypatch, capsys):
        self.tmp, self.patch, self.capsys = tmp, monkeypatch, capsys
        self.home, self.bin = tmp / "home", tmp / "bin"
        self.home.mkdir()
        self.bin.mkdir()
        self.env = {
            "HOME": str(self.home), "PATH": str(self.bin) + os.pathsep + os.defpath,
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
        }
        # The helper, called in this process, starts its children with this process's
        # environment, so that environment is replaced whole, key by key, for the test.
        for key in list(os.environ):
            if key not in self.env:
                monkeypatch.delenv(key)
        for key, value in self.env.items():
            monkeypatch.setenv(key, value)
        self._module = None
        self.target, self.backup = tmp / "settings.json", tmp / "backup"
        write_json(self.target, CLAUDE)
        self.target.chmod(0o640)
        self.before = self.target.read_bytes()

    @property
    def module(self):
        if self._module is None:
            if not TOOL.exists():
                pytest.fail("relay-cutover is not implemented")
            loader = importlib.machinery.SourceFileLoader("relay_cutover", str(TOOL))
            spec = importlib.util.spec_from_loader(loader.name, loader)
            self._module = importlib.util.module_from_spec(spec)
            loader.exec_module(self._module)
            self.real_process_rows = self._module.process_rows
            self.patch.setattr(self._module, "process_rows", lambda: [])
        return self._module

    def setenv(self, key, value):
        """One more variable, in the box's environment and this process's alike."""
        self.env[key] = value
        self.patch.setenv(key, value)

    def call(self, *args):
        code = self.module.main([str(a) for a in args])
        output = self.capsys.readouterr()
        return SimpleNamespace(code=code, out=output.out, err=output.err)

    def run(self, *args):
        result = subprocess.run([str(a) for a in args], env=self.env,
                                capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()

    def script(self, path, source):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/usr/bin/python3\n" + source)
        path.chmod(0o700)
        return path

    def ready(self, harness="claude-code"):
        runtime = self.home / ".local/share/relay/v0.1.1/node_modules/relay/bin/relay.js"
        runtime.parent.mkdir(parents=True, exist_ok=True)
        runtime.write_text('console.log("relay 0.1.1");\n')
        subscribers = self.home / ".config/relay/subscribers.json"
        subscribers.parent.mkdir(parents=True, exist_ok=True)
        subscribers.parent.chmod(0o700)
        subscribers.write_bytes((ROOT / "relay/subscribers.template.json").read_bytes().replace(
            b"@HOME@", str(self.home).encode()))
        subscribers.chmod(0o600)
        version = "2.1.302 (Claude Code)" if harness == "claude-code" else "codex-cli 0.163.0"
        self.script(self.bin / ("claude" if harness == "claude-code" else "codex"),
                    "import sys\nassert sys.argv[1:] == ['--version']\nprint(" + repr(version) + ")\n")
        evidence = self.home / "d/ops/docs/runbooks" / f"relay-guard-evidence-{harness}.json"
        write_json(evidence, {"schema": 1, "harness": harness, "version": version,
                              "probes": [{"event": "PreToolUse", "reply": reply,
                                          "outerMs": 600000, "passed": True}
                                         for reply in ("refuse", "context")]})
        return runtime, subscribers, evidence

    def images(self):
        name = str(self.target).replace("/", "_")
        return (self.backup / (name + ".before-guard"),
                self.backup / (name + ".after-guard"))

    def retire(self):
        return self.call("retire-native-guard", "--target", self.target, "--backup", self.backup)

    def restore(self, artifact=None):
        extra = ["--artifact", artifact] if artifact else []
        return self.call("restore", "--target", self.target, "--backup", self.backup, *extra)

    def artifact(self, before, after):
        path = self.tmp / "artifact.json"
        write_json(path, {"schema": 1, "harness": "claude-code", "evidence": None,
                          "changes": [{"path": str(self.target),
                                       "before": before.decode(), "after": after.decode()}]})
        launcher = self.script(self.bin / "relay", """import json, sys
from pathlib import Path
assert sys.argv[1:3] == ['rollback', '--artifact'] and len(sys.argv) == 4
artifact = json.loads(Path(sys.argv[3]).read_text())
for change in artifact['changes']:
    target = Path(change['path'])
    assert target.read_text() == change['after']
    target.write_text(change['before'])
""")
        self.setenv("RELAY_CUTOVER_RELAY", str(launcher))
        return path

    def familiar_repo(self):
        root = self.home / "d/familiar"
        root.mkdir(parents=True)
        self.run("git", "init", "-q", "-b", "main", root)
        (root / ".gitignore").write_text("node_modules/\n")
        (root / "source.js").write_text("original\n")
        (root / "package-lock.json").write_text("{}\n")
        self.script(root / "bin/familiar", "raise SystemExit('familiar must never run')\n")
        self.run("git", "-C", root, "add", ".")
        self.run("git", "-C", root, "commit", "-qm", "initial")
        return root, self.run("git", "-C", root, "rev-parse", "HEAD")


@pytest.fixture
def box(tmp_path, monkeypatch, capsys):
    return Sandbox(tmp_path, monkeypatch, capsys)


@pytest.mark.parametrize("row", [(41, "claude", "/elsewhere/claude"),
                                 (42, "node", "CLAUDE_VERSION"),
                                 (43, "codex", "/elsewhere/codex")])
def test_no_live_flags_claude_by_comm_and_version_exe(box, row):
    pid, comm, exe = row
    if exe == "CLAUDE_VERSION":
        exe = str(box.home / ".local/share/claude/versions/2.1.302")
    box.ready("codex" if comm == "codex" else "claude-code")
    box.patch.setattr(box.module, "process_rows", lambda: [(pid, comm, exe)])
    result = box.call("preflight", "--harness", "codex" if comm == "codex" else "claude-code")
    assert result.code == 1
    assert "relay-cutover: no-live:" in result.err and str(pid) in result.err
    assert len(result.err.splitlines()) == 1


def test_no_live_passes_on_unrelated(box):
    box.ready()
    box.patch.setattr(box.module, "process_rows", lambda: [
        (44, "node", "/usr/bin/node"), (45, "claude-helper", "/tmp/claude"),
        (46, "codex", "/tmp/codex"),
    ])
    assert box.call("preflight", "--harness", "claude-code").code == 0


@pytest.mark.parametrize("harness,comm", [("claude-code", "claude"), ("codex", "codex")])
def test_no_live_checks_comm_when_exe_access_is_denied(box, harness, comm):
    box.ready(harness)
    module = box.module
    proc = box.tmp / "proc/101"
    proc.mkdir(parents=True)
    (proc / "comm").write_text(comm + "\n")
    glob, readlink = Path.glob, Path.readlink

    def proc_glob(path, pattern):
        return iter([proc]) if path == Path("/proc") else glob(path, pattern)

    def denied_exe(path):
        if path == proc / "exe":
            raise PermissionError("system exe is unreadable")
        return readlink(path)

    box.patch.setattr(Path, "glob", proc_glob)
    box.patch.setattr(Path, "readlink", denied_exe)
    box.patch.setattr(module, "process_rows", box.real_process_rows)
    result = box.call("preflight", "--harness", harness)
    assert result.code == 1 and "relay-cutover: no-live:" in result.err
    assert "101" in result.err and "live " + harness in result.err


def test_runtime_reports_missing_relay(box):
    runtime, _, _ = box.ready()
    runtime.unlink()
    result = box.call("preflight", "--harness", "claude-code")
    assert result.code == 1
    assert "relay-cutover: runtime:" in result.err and "missing" in result.err


@pytest.mark.parametrize("banner", ["0.1.1", "relay 0.1.10", "prefix relay 0.1.1"])
def test_runtime_requires_exact_known_banner(box, banner):
    runtime, _, _ = box.ready()
    runtime.write_text("console.log(" + json.dumps(banner) + ");\n")
    result = box.call("preflight", "--harness", "claude-code")
    assert result.code == 1 and "relay-cutover: runtime:" in result.err


@pytest.mark.parametrize("directory", [False, True])
def test_subscribers_reports_mode_0644(box, directory):
    _, subscribers, _ = box.ready()
    changed = subscribers.parent if directory else subscribers
    changed.chmod(0o644)
    try:
        result = box.call("preflight", "--harness", "claude-code")
    finally:
        changed.chmod(0o700 if directory else 0o600)
    assert result.code == 1
    assert "relay-cutover: subscribers:" in result.err and "0644" in result.err


def test_subscribers_reports_content_drift(box):
    _, subscribers, _ = box.ready()
    subscribers.write_text(subscribers.read_text() + "\n")
    result = box.call("preflight", "--harness", "claude-code")
    assert result.code == 1 and "relay-cutover: subscribers:" in result.err
    assert "content" in result.err


def test_evidence_reports_version_mismatch(box):
    _, _, path = box.ready()
    evidence = json.loads(path.read_text())
    evidence["version"] = "2.1.300 (Claude Code)"
    write_json(path, evidence)
    result = box.call("preflight", "--harness", "claude-code")
    assert result.code == 1 and "relay-cutover: evidence:" in result.err
    assert "2.1.300 (Claude Code)" in result.err and "2.1.302 (Claude Code)" in result.err
    assert "rerun the ops relay-guard probe or update the harness" in result.err


def test_evidence_absent_harness_passes(box):
    box.ready()
    (box.bin / "claude").unlink()
    result = box.call("preflight", "--harness", "claude-code")
    assert result.code == 0 and "absent" in result.out


def test_familiar_source_head_and_working_tree(box):
    root, head = box.familiar_repo()
    (root / "node_modules").mkdir()
    (root / "node_modules/ignored").write_text("ignored\n")
    assert box.call("familiar-source", "--head", head).code == 0
    result = box.call("familiar-source", "--head", "0" * 40)
    assert result.code == 1 and "HEAD" in result.err
    for path in (root / "source.js", root / "package-lock.json"):
        before = path.read_bytes()
        path.write_text("modified\n")
        result = box.call("familiar-source", "--head", head)
        assert result.code == 1 and "working tree" in result.err
        path.write_bytes(before)


def test_familiar_source_ignores_a_stale_live_index(box):
    root, _ = box.familiar_repo()
    index = root / ".git/index"
    old_index = index.read_bytes()
    (root / "added.js").write_text("synced new source\n")
    (root / "package-lock.json").write_text('{"new": true}\n')
    box.run("git", "-C", root, "add", ".")
    box.run("git", "-C", root, "commit", "-qm", "synced commit")
    head = box.run("git", "-C", root, "rev-parse", "HEAD")
    index.write_bytes(old_index)
    assert box.call("familiar-source", "--head", head).code == 0
    assert index.read_bytes() == old_index
    (root / "added.js").write_text("changed\n")
    assert box.call("familiar-source", "--head", head).code == 1
    assert index.read_bytes() == old_index


def test_familiar_check_relay_and_native_sides(box):
    root = box.home / "d/familiar"
    box.script(root / "bin/familiar", "import sys\nassert sys.argv[1:] == ['hook', '--help']\n")
    assert box.call("familiar-check", "--expect", "native").code == 0
    package = root / "node_modules/relay/package.json"
    write_json(package, {"version": "0.1.1"})
    assert box.call("familiar-check", "--expect", "native").code == 1
    box.script(root / "bin/familiar", "import sys\nassert sys.argv[1:] == ['observe', '--help']\n")
    assert box.call("familiar-check", "--expect", "relay").code == 0
    write_json(package, {"version": "0.1.0"})
    assert box.call("familiar-check", "--expect", "relay").code == 1
    write_json(package, {"version": "0.1.1"})
    box.script(root / "bin/familiar", "raise SystemExit(3)\n")
    assert box.call("familiar-check", "--expect", "relay").code == 1


def test_familiar_checks_use_explicit_root_without_changing_home(box):
    """A pilot names its owned scratch clone with --root: the two read-only familiar checks read
    only that clone, never HOME's live checkout, and run with the actual HOME and SSH agent."""
    live, live_head = box.familiar_repo()  # its bin/familiar refuses to run
    live_files = {path: path.read_bytes() for path in live.rglob("*") if path.is_file()}
    scratch = box.tmp / "pilot/0123456789abcdef/familiar"
    scratch.mkdir(parents=True)
    box.run("git", "init", "-q", "-b", "main", scratch)
    (scratch / ".gitignore").write_text("node_modules/\n")
    (scratch / "source.js").write_text("scratch clone\n")
    seen = box.tmp / "seen.json"
    box.script(scratch / "bin/familiar", "import json, os, sys\n"
               f"open({str(seen)!r}, 'w').write(json.dumps({{'argv': sys.argv[1:], "
               "'home': os.environ.get('HOME'), 'agent': os.environ.get('SSH_AUTH_SOCK')}))\n")
    box.run("git", "-C", scratch, "add", ".")
    box.run("git", "-C", scratch, "commit", "-qm", "scratch")
    head = box.run("git", "-C", scratch, "rev-parse", "HEAD")
    agent = str(box.tmp / "agent.sock")
    box.setenv("SSH_AUTH_SOCK", agent)
    home = box.env["HOME"]

    def helper(*args):
        """The helper as its own process, with the box's HOME and agent as its environment."""
        result = subprocess.run([str(TOOL), *map(str, args)], env=box.env,
                                capture_output=True, text=True)
        return result.returncode, result.stderr

    assert helper("familiar-source", "--head", head, "--root", scratch)[0] == 0
    assert helper("familiar-source", "--head", live_head, "--root", scratch)[0] == 1
    assert helper("familiar-source", "--head", head)[0] == 1  # the default stays main
    (scratch / "source.js").write_text("changed\n")
    code, err = helper("familiar-source", "--head", head, "--root", scratch)
    assert code == 1 and "working tree" in err
    (scratch / "source.js").write_text("scratch clone\n")

    assert helper("familiar-check", "--expect", "native", "--root", scratch)[0] == 0
    assert json.loads(seen.read_text()) == {"argv": ["hook", "--help"], "home": home,
                                            "agent": agent}
    write_json(scratch / "node_modules/relay/package.json", {"version": "0.1.1"})
    assert helper("familiar-check", "--expect", "native", "--root", scratch)[0] == 1
    assert helper("familiar-check", "--expect", "relay", "--root", scratch)[0] == 0
    assert json.loads(seen.read_text()) == {"argv": ["observe", "--help"], "home": home,
                                            "agent": agent}

    # Only an absolute directory names a root; nothing falls back to the live checkout.
    (box.tmp / "linked").symlink_to(scratch)
    for bad in ("relative/familiar", box.tmp / "absent", box.target, box.tmp / "linked"):
        code, err = helper("familiar-check", "--expect", "native", "--root", bad)
        assert code == 1 and "--root" in err
        assert helper("familiar-source", "--head", head, "--root", bad)[0] == 1
    assert box.env["HOME"] == home and box.env["SSH_AUTH_SOCK"] == agent
    assert {path: path.read_bytes() for path in live.rglob("*") if path.is_file()} == live_files


@pytest.mark.parametrize("command,args", [
    ("preflight", ["--harness", "codex"]),
    ("familiar-source", ["--head", "1" * 40]),
    ("familiar-check", ["--expect", "native"]),
])
def test_remote_repeats_the_same_check_with_safe_arguments(box, command, args):
    box.script(box.bin / "ssh", "import json, sys\nprint(json.dumps(sys.argv[1:]))\n")
    result = box.call(command, *args, "--host", "test-host")
    assert result.code == 0
    invocation = json.loads(result.out)
    assert invocation == ["-4", "-o", "BatchMode=yes", "test-host",
                          "~/d/hq/tools/relay-cutover " + " ".join([command, *args])]
    assert box.call(command, *args, "--host=-oProxyCommand=anything").code == 1


def test_remote_preserves_each_check_failure_and_success_output(box):
    box.script(box.bin / "ssh", """import sys
print('relay-cutover: runtime: ok')
print('relay-cutover: no-live: live process 42', file=sys.stderr)
print('relay-cutover: subscribers: content drift', file=sys.stderr)
raise SystemExit(1)
""")
    result = box.call("preflight", "--harness", "codex", "--host", "test-host")
    assert result.code == 1
    assert result.out == "relay-cutover: runtime: ok\n"
    assert result.err.splitlines() == [
        "relay-cutover: no-live: live process 42",
        "relay-cutover: subscribers: content drift",
    ]


def test_retire_removes_only_the_native_guard_group(box):
    assert box.retire().code == 0
    after = json.loads(box.target.read_text())
    expected = copy.deepcopy(CLAUDE)
    expected["hooks"]["PreToolUse"].pop()
    assert after == expected
    assert box.target.read_bytes().endswith(b"\n")
    assert stat.S_IMODE(box.target.stat().st_mode) == 0o640


def test_retire_writes_exact_before_and_after_images(box):
    assert box.retire().code == 0
    before, after = box.images()
    assert before.read_bytes() == box.before
    assert after.read_bytes() == box.target.read_bytes()
    assert stat.S_IMODE(before.stat().st_mode) == 0o640
    assert stat.S_IMODE(after.stat().st_mode) == 0o640


def test_retire_persists_both_images_before_replacing(box):
    atomic_write = box.module.atomic_write
    before, after = box.images()

    def fail_second(path, data, mode):
        if path == after:
            assert before.read_bytes() == box.before
            raise OSError("injected second image failure")
        atomic_write(path, data, mode)

    box.patch.setattr(box.module, "atomic_write", fail_second)
    assert box.retire().code == 1
    assert box.target.read_bytes() == box.before
    assert before.read_bytes() == box.before and not after.exists()
    box.patch.setattr(box.module, "atomic_write", atomic_write)
    result = box.retire()
    assert result.code == 1 and "exists" in result.err
    assert box.target.read_bytes() == box.before and not after.exists()
    assert box.restore().code == 0


def test_retire_fsyncs_images_and_directory_before_replacement(box):
    target_directory = box.tmp / "targets"
    target_directory.mkdir()
    box.target = box.target.rename(target_directory / "settings.json")
    caller_created = box.tmp / "recovery/caller-created"
    caller_created.mkdir(parents=True)
    box.backup = caller_created / "new/backups"
    replace, fsync = box.module.os.replace, box.module.os.fsync
    synced = []
    before, after = box.images()

    def track_sync(fd):
        synced.append(os.readlink(f"/proc/self/fd/{fd}"))
        fsync(fd)

    def check_replace(source, target):
        if target == box.target:
            assert before.read_bytes() == box.before and after.exists()
            image_syncs = [p for p in synced if str(box.backup) + "/" in p]
            assert len(image_syncs) == 2
            for directory in (box.backup, box.backup.parent, caller_created,
                              caller_created.parent, box.tmp):
                assert str(directory) in synced, f"unsynced backup ancestor: {directory}"
                assert synced.index(str(directory)) < synced.index(image_syncs[0])
            backup_syncs = [p for p in synced if p == str(box.backup)
                            or p.startswith(str(box.backup) + "/")]
            assert backup_syncs[-4:] == [image_syncs[0], str(box.backup),
                                        image_syncs[1], str(box.backup)]
        replace(source, target)

    box.patch.setattr(box.module.os, "fsync", track_sync)
    box.patch.setattr(box.module.os, "replace", check_replace)
    assert box.retire().code == 0


def test_retire_directory_sync_failure_keeps_target_and_retry_syncs_existing_parents(box):
    box.backup = box.tmp / "recovery/new/backups"
    fsync, replace = box.module.os.fsync, box.module.os.replace

    def fail_parent_sync(fd):
        if os.readlink(f"/proc/self/fd/{fd}") == str(box.backup.parent):
            raise OSError("injected backup-parent fsync failure")
        fsync(fd)

    box.patch.setattr(box.module.os, "fsync", fail_parent_sync)
    assert box.retire().code == 1
    assert box.target.read_bytes() == box.before
    assert not any(path.exists() for path in box.images())
    synced = []

    def track_sync(fd):
        synced.append(os.readlink(f"/proc/self/fd/{fd}"))
        fsync(fd)

    def check_replace(source, target):
        if target == box.target:
            assert str(box.backup.parent) in synced
        replace(source, target)

    box.patch.setattr(box.module.os, "fsync", track_sync)
    box.patch.setattr(box.module.os, "replace", check_replace)
    assert box.retire().code == 0


def test_retire_failure_after_replace_is_restorable(box):
    replace = box.module.os.replace

    def fail_after_replace(source, target):
        replace(source, target)
        if target == box.target:
            raise OSError("injected failure after target rename")

    box.patch.setattr(box.module.os, "replace", fail_after_replace)
    assert box.retire().code == 1
    assert box.target.read_bytes() == box.images()[1].read_bytes() != box.before
    box.patch.setattr(box.module.os, "replace", replace)
    assert box.restore().code == 0
    assert box.target.read_bytes() == box.before


@pytest.mark.parametrize("case", ["absent", "duplicate", "shared", "symlink", "relative", "rerun"])
def test_retire_refuses_absent_duplicate_shared_symlink_relative_and_rerun(box, case):
    target = box.target
    data = copy.deepcopy(CLAUDE)
    if case == "absent":
        data["hooks"]["PreToolUse"].pop()
    elif case == "duplicate":
        data["hooks"]["PreToolUse"].append(copy.deepcopy(GUARD))
    elif case == "shared":
        data["hooks"]["PreToolUse"][-1]["hooks"].append({"type": "command", "command": "other"})
    elif case == "symlink":
        target = box.tmp / "linked.json"
        target.symlink_to(box.target)
    elif case == "relative":
        target = Path("settings.json")
    elif case == "rerun":
        assert box.retire().code == 0
    if case in {"absent", "duplicate", "shared"}:
        write_json(box.target, data)
    current = box.target.read_bytes()
    existing = {p.name: p.read_bytes() for p in box.backup.glob("*")}
    result = box.call("retire-native-guard", "--target", target, "--backup", box.backup)
    assert result.code == 1 and "relay-cutover: retire-native-guard:" in result.err
    assert box.target.read_bytes() == current
    assert {p.name: p.read_bytes() for p in box.backup.glob("*")} == existing


def test_restore_after_guard_removal_only(box):
    assert box.retire().code == 0
    assert box.restore().code == 0
    assert box.target.read_bytes() == box.before
    assert box.restore().code == 0


def test_restore_after_relay_apply(box):
    assert box.retire().code == 0
    artifact = box.artifact(box.target.read_bytes(), b'{"hooks": {"Stop": []}}\n')
    box.target.write_bytes(b'{"hooks": {"Stop": []}}\n')
    assert box.restore(artifact).code == 0
    assert box.target.read_bytes() == box.before
    assert box.restore(artifact).code == 0


def test_restore_after_failed_apply(box):
    assert box.retire().code == 0
    artifact = box.artifact(box.target.read_bytes(), b'{"hooks": {}}\n')
    # Applying wrote the artifact but failed before replacing the target.
    assert box.restore(artifact).code == 0
    assert box.target.read_bytes() == box.before


def test_restore_without_guard_images(box):
    write_json(box.target, CODEX)
    before, after = box.target.read_bytes(), b'{"hooks": {"Stop": []}}\n'
    artifact = box.artifact(before, after)
    box.target.write_bytes(after)
    assert box.restore(artifact).code == 0
    assert box.target.read_bytes() == before
    assert box.restore(artifact).code == 0


def test_restore_refuses_unknown_bytes_and_writes_nothing(box):
    assert box.retire().code == 0
    artifact = box.artifact(box.target.read_bytes(), b'{"hooks": {}}\n')
    box.target.write_bytes(b"unknown target bytes\n")
    images = {p: p.read_bytes() for p in box.backup.iterdir()}
    result = box.restore(artifact)
    assert result.code == 1 and "matches none" in result.err
    assert box.target.read_bytes() == b"unknown target bytes\n"
    assert {p: p.read_bytes() for p in box.backup.iterdir()} == images


def test_restore_stops_if_rollback_does_not_reach_its_before_image(box):
    assert box.retire().code == 0
    artifact = box.artifact(box.target.read_bytes(), b'{"hooks": {}}\n')
    box.target.write_bytes(b'{"hooks": {}}\n')
    box.script(box.bin / "relay", "pass\n")
    result = box.restore(artifact)
    assert result.code == 1 and "artifact.after" in result.err
    assert box.target.read_bytes() == b'{"hooks": {}}\n'


def test_restore_refuses_artifact_missing_before_without_writing(box):
    artifact = box.tmp / "malformed.json"
    write_json(artifact, {"schema": 1, "changes": [
        {"path": str(box.target), "after": "other bytes"},
    ]})
    result = box.restore(artifact)
    assert result.code == 1 and "artifact" in result.err
    assert box.target.read_bytes() == box.before


@pytest.mark.parametrize("command", ["restore", "verify"])
@pytest.mark.parametrize("linked", [False, True])
def test_other_target_commands_refuse_relative_paths_and_symlinks(box, command, linked):
    target = Path("relative.json")
    if linked:
        target = box.tmp / "link.json"
        target.symlink_to(box.target)
    extra = ["--backup", box.backup] if command == "restore" else ["--expect", box.target]
    result = box.call(command, "--target", target, *extra)
    assert result.code == 1 and "absolute and not a symlink" in result.err
    assert box.target.read_bytes() == box.before


def test_verify_ignores_model_and_effort_keys(box):
    expected = box.tmp / "expected.json"
    data = copy.deepcopy(CLAUDE)
    data.update(model="another-pick", effortLevel="high")
    write_json(expected, data)
    assert box.call("verify", "--target", box.target, "--expect", expected).code == 0


def test_verify_diff_names_the_changed_event(box):
    expected = box.tmp / "expected.json"
    data = copy.deepcopy(CLAUDE)
    data["hooks"]["Stop"] = []
    write_json(expected, data)
    result = box.call("verify", "--target", box.target, "--expect", expected)
    assert result.code == 1 and "relay-cutover: verify:" in result.err
    assert '"Stop"' in result.out and "--- " in result.out and "+++ " in result.out


def test_cli_reports_invalid_json_without_traceback(box):
    if not TOOL.exists():
        pytest.fail("relay-cutover is not implemented")
    box.target.write_text("broken JSON\n")
    result = subprocess.run([str(TOOL), "retire-native-guard", "--target", str(box.target),
                             "--backup", str(box.backup)], env=box.env,
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert result.stderr.startswith("relay-cutover: retire-native-guard:")
    assert len(result.stderr.splitlines()) == 1
    assert not box.backup.exists()


@pytest.mark.parametrize("args", [[], ["preflight", "--harness", "unknown"]])
def test_cli_usage_failures_are_one_line_and_exit_one(box, args):
    result = subprocess.run([str(TOOL), *args], env=box.env,
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert result.stderr.startswith("relay-cutover: arguments:")
    assert len(result.stderr.splitlines()) == 1
