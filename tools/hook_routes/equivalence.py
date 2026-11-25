"""Compare a digest-addressed relay candidate to its native callers in private checkouts."""
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
from typing import Literal

from . import relay_runtime

__all__ = ["DEFAULT_CASES", "EvidenceLine", "run"]

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/hook-equivalence"
DEFAULT_CASES = FIXTURES / "cases.json"
CASES = {
    "clean-checkout": {"profile", "stale", "index", "capture"},
    "stale-lore-fragment": {"stale"}, "index-needing-repair": {"index"},
    "capture-queue-empty": {"capture"}, "capture-queue-nonempty": {"capture"},
    "profile-unresolved": {"profile"}, "harness-state-refresh": {"refresh"},
}
POLICIES = {
    ("lore", "hook", "profile-notice"): ("profile", "notice"),
    ("lore", "hook", "stale-notice"): ("stale", "notice"),
    ("git-index-health", "--session-start"): ("index", "notice"),
    ("mindful", "notice", "session-start"): ("capture", "notice"),
    ("harness-state-refresh",): ("refresh", "observer"),
    ("tasks", "hook", "halt-notice"): ("halt", "notice"),
    ("tasks", "hook", "claim-guard"): ("claim", "guard"),
}
# What a replayed subscriber runs by name: the owner commands, and the env that wraps an observer.
COMMANDS = ("lore", "mindful", "tasks", "git-index-health", "harness-state-refresh", "env")
ADDRESS = re.compile(r"(v[0-9]+\.[0-9]+\.[0-9]+)-([0-9a-f]{12})/relay/subscribers\.json")


@dataclass(frozen=True)
class EvidenceLine:
    binding: str
    policy: str
    status: Literal["passed", "failed"]
    line: str


def _corpus(path):
    identity = ("harness", "version", "sessionMode", "event")
    templates = (FIXTURES / "events.json").read_bytes()
    events = {tuple(event[key] for key in identity): event for event in json.loads(templates)}
    rows = json.loads((path / "cases.json" if path.is_dir() else path).read_bytes())
    if not isinstance(rows, list) or not rows:
        raise ValueError("empty or invalid replay corpus")
    for row in rows:
        fields = {"case", "harness", "event", "version", "sessionMode", "source"}
        if set(row) != fields or any(not isinstance(v, str) or not v.strip() for v in row.values()):
            raise ValueError(f"invalid fixture descriptor: {row!r}")
        if row["case"] not in CASES:
            raise ValueError(f"unknown fixture case: {row['case']}")
        if (row["harness"] not in {"claude-code", "codex"}
                or row["event"] != ("Stop" if row["case"] == "harness-state-refresh" else "SessionStart")
                or row["sessionMode"] not in {"interactive", "non-interactive"}
                or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", row["version"])):
            raise ValueError(f"unknown fixture target: {row!r}")
        target = tuple(row[key] for key in identity)
        if target not in events:
            raise ValueError(f"unrecorded fixture identity: {target}")
        row["payload"] = events[target]["payload"]
        row["upstream"] = events[target]["upstream"]
        row["changes"] = events[target]["changes"]
        row["templateSha256"] = sha256(templates).hexdigest()
    return rows


def _reviewed(directory):
    manifest = json.loads((directory / "manifest.json").read_bytes())
    if set(manifest) != {"kind", "files"} or manifest["kind"] != "candidate":
        raise ValueError("expected a frozen candidate manifest")
    files = {}
    for name, digest in manifest["files"].items():
        path = directory / name
        if Path(name).is_absolute() or path.resolve() != directory.resolve() / name or ".." in Path(name).parts:
            raise ValueError(f"unsafe candidate filename: {name}")
        data = path.read_bytes()
        if sha256(data).hexdigest() != digest:
            raise ValueError(f"candidate digest mismatch: {name}")
        files[name] = data
    return files


def _policies(table, config, home):
    legacy = {tuple(arg.replace("~/", str(home) + "/", 1) if arg.startswith("~/") else arg
                    for arg in sub.argv): sub.role for sub in table.subscribers.values()
              if sub.policy in {"familiar", "ops-guard"}}
    result = {}
    for sub in config["subscribers"]:
        argv = tuple(sub["argv"])
        if argv in POLICIES:
            policy, role = POLICIES[argv]
            if policy == "refresh" and sub.get("registry") != "occurrence":
                raise ValueError("refresh must be an occurrence observer")
        elif argv in legacy:
            policy, role = "existing", legacy[argv]
        else:
            raise ValueError(f"unknown candidate subscriber argv: {argv}")
        if role != sub["role"]:
            raise ValueError(f"unexpected {policy} role: {sub['role']}")
        if sub["name"] in result:
            raise ValueError(f"duplicate candidate subscriber: {sub['name']}")
        result[sub["name"]] = policy
    return result


def _bindings(table, files, home, scratch):
    used = set()
    for key, settings in table.homes.items():
        if settings.harness == "agy" or settings.path not in files:
            continue
        for event, groups in json.loads(files[settings.path])["hooks"].items():
            for group in groups:
                for hook in group["hooks"]:
                    argv = shlex.split(hook["command"])
                    if "--subscribers" not in argv:
                        continue
                    if len(argv) != 10 or argv[2:6] != ["hook", "--harness", settings.harness, "--outer-ms"] or argv[7] != "--subscribers":
                        raise ValueError(f"unknown candidate relay command: {argv}")
                    address = Path(argv[8]).relative_to(home / ".config/relay").as_posix()
                    if re.fullmatch(r"v[0-9.]+/relay/subscribers\.json", address):
                        continue
                    match = ADDRESS.fullmatch(address)
                    if not match or address not in files:
                        raise ValueError(f"unknown candidate address: {address}")
                    digest = sha256(files[address]).hexdigest()
                    version = match[1]
                    if (not digest.startswith(match[2]) or version not in table.runtimes
                            or tuple(argv[:2]) != tuple(table.runtimes[version].argv(home))):
                        raise ValueError(f"candidate runtime or digest mismatch: {address}")
                    used.add(address)
                    config = json.loads(files[address])
                    policies = _policies(table, config, home)
                    if event not in {binding.event for binding in settings.bindings}:
                        raise ValueError(f"unknown candidate binding {key}/{event}")
                    if event not in {"SessionStart", "Stop", "SubagentStop"}:
                        continue
                    if argv[-1] != event or int(argv[6]) <= 0 or hook["timeout"] * 1000 < int(argv[6]):
                        raise ValueError(f"invalid candidate event or budget: {argv}")
                    package = relay_runtime.package_for(table, version, home)
                    # Only the selected runtime decides which subscribers this event invokes.
                    payload = dict(config=config, harness=settings.harness, event=event, outerMs=int(argv[6]))
                    with tempfile.TemporaryDirectory(dir=scratch) as budget_dir:
                        admission = _sandbox(Path(budget_dir), [(package, Path("/packages/relay"))], "budget", payload)
                    selected = {name: policies[name] for name in admission["subscribers"]}
                    yield key, settings.harness, event, version, package, int(argv[6]), files[address], selected
    if used != {name for name in files if ADDRESS.fullmatch(name)}:
        raise ValueError("candidate contains unreferenced subscriber bytes")


def _source(name, path_env):
    path = shutil.which(name, path=path_env)
    if not path:
        raise ValueError(f"missing fixture owner command: {name}")
    return Path(path).resolve(strict=True)


def _copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))
    else:
        shutil.copy2(source, target)


def _assets(table, root, path_env, selected, home):
    """Only named sources enter the namespace. Owner binaries run with no host filesystem view."""
    policies = set(selected.values())
    ops = home / "d/ops"
    lore = home / "d/lore"
    binds = []
    dest = root / "home/d"
    for name in ("candidate", "fixture-bin", "owners", "home/.config", "home/.local/state", "home/.local/share"):
        (root / name).mkdir(parents=True, exist_ok=True)
    if "existing" in policies:
        # The frozen argv embeds the deployment home. Expose just this package there, read-only.
        familiar = home / "d/familiar"
        for name in ("package.json", "bin", "src", "node_modules"):
            binds.append(((familiar / name).resolve(strict=True), familiar / name))
    if policies & {"profile", "stale"}:
        found = shutil.which("lore", path=path_env)
        source = Path(found).resolve() if found else lore / "bin/lore"
        # Today's oracle belongs to the deployed checkout, independently of PATH.
        for name in ("src/lore", "profiles", "bin/lore", "hooks/claude-profile"):
            _copy(lore / name, dest / "lore" / name)
        owner = root / "replacement-lore"
        owner_root = source.parent.parent
        if (owner_root / "src/lore").is_dir():
            for name in ("src/lore", "profiles"):
                _copy(owner_root / name, owner / name)
        _copy(source, owner / "bin/lore")
        (root / "owners/lore").symlink_to("../home/d/lore/bin/lore")
    if policies & {"stale", "index"}:
        for name in ("hooks/claude-sessionstart", "bin/git-index-health", "bin/linked.py"):
            _copy(ops / name, dest / "ops" / name)
        for name in ("ops-projects", "assemble-instructions"):
            owner = "ops" if name == "ops-projects" else "lore"
            _copy(FIXTURES / name, dest / owner / "bin" / name)
    if "index" in policies:
        binary = _source("git-index-health", path_env)
        _copy(binary, dest / "hostkit/bin/git-index-health")
        _copy(binary.parents[1] / "src/hostkit", dest / "hostkit/src/hostkit")
        (root / "owners/git-index-health").symlink_to("../home/d/hostkit/bin/git-index-health")
    if "capture" in policies:
        for name in ("hooks/capture-notice", "bin/mindful-op"):
            _copy(ops / name, dest / "ops" / name)
        binary = _source("mindful", path_env)
        binds.append((binary.parents[1], Path("/packages/mindful")))
        (root / "owners/mindful").symlink_to("/packages/mindful/bin/mindful")
    if "refresh" in policies:
        for name in ("harness-state-clean", "harness-state-refresh", "codex-trust", "harness_state.py", "live-picks"):
            _copy(table.root / ".githooks" / name, dest / "hq/.githooks" / name)
        for name in ("harnesses.toml", ".gitattributes"):
            _copy(table.root / name, dest / "hq" / name)
        (root / "owners/harness-state-refresh").symlink_to("../home/d/hq/.githooks/harness-state-refresh")
    _copy(_source("tasks", path_env), root / "owners/tasks")
    _copy(FIXTURES / "owner.py", root / "owner.py")
    for name in COMMANDS:
        (root / "fixture-bin" / name).symlink_to("../owner.py")
    return binds


def _listed(tree, search_path):
    """Put the replay's commands first in the list a schema-3 file searches."""
    commands = tree / "listed-bin"
    for entry in search_path:
        target = Path(re.sub(r"^/bin(?=/|$)", "/usr/bin", entry))  # As _sandbox links it.
        toolchain = target.is_relative_to("/usr")
        if toolchain and not target.is_dir():
            continue  # relay passes over it, and the read-only toolchain cannot grow it.
        commands.mkdir()
        for name in COMMANDS:
            # owner.py runs /usr/bin/env, so the toolchain's own stays itself.
            if not (toolchain and name == "env"):
                (commands / name).symlink_to("/fixture/owner.py")
        return [(commands, target)]
    raise ValueError(f"the replay can use no directory of the search path {search_path}")


def _sandbox(tree, binds, action, payload=None):
    # Admission reads config, while a real hook identifies its invoking harness
    # from /proc. Every execution side uses the same private namespace layout.
    root = tree.resolve() if action == "budget" else Path("/fixture")
    home = root / "home"
    env = {"HOME": str(home), "PATH": f"{root}/fixture-bin:/usr/bin", "LANG": "C.UTF-8",
           "XDG_CONFIG_HOME": str(home / ".config"), "XDG_DATA_HOME": str(home / ".local/share"),
           "XDG_STATE_HOME": str(home / ".local/state"), "GIT_CONFIG_GLOBAL": str(home / ".gitconfig"),
           "GIT_CONFIG_NOSYSTEM": "1"}
    package = next(source for source, target in binds if target == Path("/packages/relay"))
    if action == "budget":
        command = ["/usr/bin/node", Path(__file__).with_name("relay_call.mjs"), package, "budget"]
    else:
        command = ["/usr/bin/bwrap", "--unshare-all", "--die-with-parent", "--new-session", "--ro-bind", "/usr", "/usr",
                   "--symlink", "usr/bin", "/bin", "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64",
                   "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--bind", str(tree), "/fixture",
                   "--ro-bind", str(FIXTURES / "exercise.py"), "/exercise.py",
                   "--ro-bind", str(FIXTURES / "hosts"), "/etc/hosts"]
        for source, target in binds:
            if target.is_relative_to("/usr"):  # The toolchain keeps its programs beside what is bound there.
                command.extend(["--overlay-src", str(target), "--overlay-src", str(source), "--ro-overlay", str(target)])
            else:
                command.extend(["--ro-bind", str(source), str(target)])
        command.extend(["--chdir", "/fixture", "--", "/usr/bin/python3", "/exercise.py", action, "/packages/relay",
                        os.readlink("/proc/self/ns/pid")])
    result = subprocess.run(command, env=env, cwd=tree, input=json.dumps(payload), capture_output=True,
                            text=True, timeout=90)
    if result.returncode:
        raise ValueError(f"fixture {action}: {result.stderr.strip() or result.returncode}")
    return json.loads(result.stdout)


def run(table, next_dir: Path, cases: Path, *, scratch: Path, path_env: str) -> list[EvidenceLine]:
    corpus = _corpus(cases)
    home = Path.home()
    scratch.mkdir(parents=True, exist_ok=True)
    bindings = list(_bindings(table, _reviewed(next_dir), home, scratch))
    lines = []
    for key, harness, event, version, package, budget, data, selected in bindings:
        relevant = {p for p in selected.values() if p in set.union(*CASES.values())}
        covered = set()
        for row in corpus:
            policies = relevant & CASES[row["case"]]
            if (row["harness"], row["event"]) != (harness, event) or not policies:
                continue
            covered.update(policies)
            with tempfile.TemporaryDirectory(dir=scratch) as temp:
                base = Path(temp)
                tree = base / "fixture"
                seed = base / "seed"
                binds = _assets(table, tree, path_env, selected, home) + [(package, Path("/packages/relay"))]
                search_path = json.loads(data).get("searchPath")
                listed = [] if search_path is None else _listed(tree, search_path)
                config = tree / "candidate/subscribers.json"
                config.write_bytes(data)
                config.chmod(0o600)
                config.parent.chmod(0o700)
                request = dict(row, home=key, selected=selected, policies=sorted(policies), budget=budget)
                (tree / "request.json").write_text(json.dumps(request))
                _sandbox(tree, binds, "prepare")
                digest = sha256((tree / "payload.json").read_bytes()).hexdigest()
                tree.rename(seed)
                results = {}
                for side in ("native", "relay"):
                    shutil.copytree(seed, tree, symlinks=True)
                    if side == "relay" and (tree / "replacement-lore").is_dir():
                        # Keep the logical path equal on both sides for profile recovery text.
                        for name in ("src", "profiles", "bin/lore"):
                            current = tree / "home/d/lore" / name
                            replacement = tree / "replacement-lore" / name
                            if current.is_dir():
                                shutil.rmtree(current)
                            else:
                                current.unlink(missing_ok=True)
                            if replacement.exists():
                                current.parent.mkdir(parents=True, exist_ok=True)
                                replacement.rename(current)
                    results[side] = _sandbox(tree, binds + listed if side == "relay" else binds, side)
                    shutil.rmtree(tree)
            for policy in sorted(policies):
                native, relay = (results[side][policy] for side in ("native", "relay"))
                passed = native["ok"] and relay["ok"] and native["value"] == relay["value"]
                status = "passed" if passed else "failed"
                details = (f"case={row['case']} source={row['source']} template=tools/fixtures/hook-equivalence/events.json "
                           f"templateSha256={row['templateSha256']} payloadSha256={digest} upstream={row['upstream']} "
                           f"changes={json.dumps(row['changes'])} fixture replay")
                if not passed:
                    details += f" native={json.dumps(native)} relay={json.dumps(relay)}"
                binding = f"{key}/{event}"
                line = (f"policyEquivalence {status} {binding} {harness} {row['version']} {row['sessionMode']} "
                        f"policy={policy} relayCommit={table.runtimes[version].commit} "
                        f"configDigest={sha256(data).hexdigest()} {details}")
                lines.append(EvidenceLine(binding, policy, status, line))
            if diagnostic := results["relay"].get("_composition"):
                lines.append(EvidenceLine(binding, "composition", "failed",
                                          f"composition failed {binding} {harness} {row['version']} {row['sessionMode']} "
                                          f"{details} diagnostic={json.dumps(diagnostic)} "
                                          f"relayCommit={table.runtimes[version].commit} configDigest={sha256(data).hexdigest()}"))
        if relevant - covered:
            raise ValueError(f"{key}/{event}: missing fixture coverage for {sorted(relevant - covered)}")
    if not lines:
        raise ValueError("candidate has no donor policy equivalence bindings")
    return lines
