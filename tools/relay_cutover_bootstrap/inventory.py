"""The cutover's read-only host inventory: one fixed operation run by `hosts.execute`.

It records identity, the child PATH, the user bus, the system toolchain and caches, Git
access to familiar-theme's pin, helper bytes, held Claude/Codex probes in both homes, the
existing relay preflight, the trusted desktop context and harness processes. Every child
runs through `hosts._run_child`, so it is owned, bounded and logged privately; replies carry
parsed values only."""
import hashlib
import json
import os
import pwd
import re
import stat
from pathlib import Path

from . import hosts
from .state import Stop

NPM_VERSION = "12.2.1"
# `claude doctor` prints this line when DISABLE_UPDATES holds updates (2.1.304's text).
HOLD_DIAGNOSTIC = "Auto-updates: disabled (set by env: DISABLE_UPDATES)"
PROBE_SECONDS = 60
DOCTOR_SECONDS = 120
PREFLIGHT_SECONDS = 180
INVENTORY_SECONDS = 600
VERSIONS = {"npm": r"\d+\.\d+\.\d+", "node": r"v\d+\.\d+\.\d+",
            "git": r"git version \d+\.\d+\.\d+\S*", "python3": r"Python \d+\.\d+\.\d+\S*"}
CLAUDE_VERSION = re.compile(r"\d+\.\d+\.\d+ \(Claude Code\)")
CODEX_VERSION = re.compile(r"codex-cli \d+\.\d+\.\d+")
CLAUDE_FAMILY = re.compile(r"\d+\.\d+\.\d+")
CODEX_FAMILY = re.compile(r"\d+\.\d+\.\d+-[A-Za-z0-9_]+(-[A-Za-z0-9_]+)*/bin/codex")
THEME_SOURCE = re.compile(r"git\+(ssh://git@[\w.-]+/[\w.-]+/[\w.-]+\.git)#([0-9a-f]{40})")
LS_REMOTE = re.compile(r"[0-9a-f]{40}\tHEAD")
NIRI_SOCKET = re.compile(r"niri\.wayland-\d+\.(\d+)\.sock")
SPAWN = re.compile(r'\s*spawn-sh-at-startup\s+"((?:[^"\\]|\\.)*)"\s*')
INCLUDE = re.compile(r'\s*include\s+"((?:[^"\\]|\\.)*)"\s*')
SURFACES = {"familiar-niri-watch": "familiar-niri watch",
            "niri-desktop": "familiar/integrations/niri-desktop"}
PREFLIGHT_CHECKS = ("no-live", "runtime", "subscribers", "evidence")
UNIT = "familiar-reap.timer"
SYSTEM_STATES = ("initializing", "starting", "running", "degraded", "maintenance", "stopping")
HELPERS = ("tools/relay-cutover-host", "tools/relay-cutover-bootstrap",
           "tools/relay-cutover-rehearse", "tools/relay-cutover", "tools/quiesce-timers",
           "relay/bin/relay", "relay/subscribers.template.json", "relay/package.json",
           "relay/package-lock.json", ".githooks/harness-state-clean")
EVIDENCE = ("docs/runbooks/relay-guard-evidence-claude-code.json",
            "docs/runbooks/relay-guard-evidence-codex.json")
CACHE_KEYS = ("npm_config_cache", "CACHE_DIR", "PYTHONPYCACHEPREFIX", "XDG_CACHE_HOME")
LIVE = ("d", "d/hq", "d/familiar", "d/ops", ".claude", ".claude-work", ".claude.json",
        ".codex", ".codex-work", ".config/relay", ".config/niri", ".local/state/familiar",
        ".local/state/hq", ".local/share/relay", ".local/share/claude")


def _text(data):
    return data.decode("utf-8", "replace").strip()


def _file_sha256(path):
    if not os.path.isfile(path):
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _probe(context, label, argv, env, timeout=PROBE_SECONDS):
    return hosts._run_child(context, label, argv, env=env, timeout=timeout)


def _process_rows():
    """This user's live processes: PID, start time, comm, exe and argv (never environ)."""
    rows = []
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        directory = f"/proc/{name}"
        try:
            if os.stat(directory).st_uid != os.getuid():
                continue
            info = hosts._proc_stat(name)
            with open(f"{directory}/comm") as stream:
                comm = stream.read().strip()
            with open(f"{directory}/cmdline", "rb") as stream:
                argv = [part.decode("utf-8", "replace")
                        for part in stream.read().split(b"\0")[:-1]]
            try:
                exe = os.readlink(f"{directory}/exe")
            except OSError:
                exe = None
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
        if info is not None and info["state"] not in ("Z", "X"):
            rows.append({"pid": int(name), "start_time": info["start_time"], "comm": comm,
                         "exe": exe, "argv": argv})
    return rows


def _hold(pid):
    """Whether one owned process holds DISABLE_UPDATES=1; no other variable is kept."""
    try:
        with open(f"/proc/{pid}/environ", "rb") as stream:
            return b"DISABLE_UPDATES=1" in stream.read().split(b"\0")
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None


def _runtime_dir():
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if not runtime or not os.path.isabs(runtime):
        return None
    try:
        info = os.lstat(runtime)
    except FileNotFoundError:
        return None
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o700):
        return None
    return runtime


def _identity(context, blockers):
    user = os.environ.get("USER")
    if not user:
        blockers.append("identity: USER is unset; tools that read it would fail")
    elif user != pwd.getpwuid(os.getuid()).pw_name:
        blockers.append("identity: USER does not name this account")
    return {"user": user or None, "uid": os.getuid(), "home": context["home"]}


def _user_bus(context, env, blockers):
    runtime = _runtime_dir()
    report = {"runtime_dir": runtime, "bus": False, "system": None, "units": {}}
    if runtime is None:
        blockers.append("user-bus: XDG_RUNTIME_DIR is unset or not this user's private "
                        "directory")
        return report
    try:
        bus = os.lstat(os.path.join(runtime, "bus"))
    except FileNotFoundError:
        bus = None
    if bus is None or not stat.S_ISSOCK(bus.st_mode):
        blockers.append("user-bus: XDG_RUNTIME_DIR has no user bus socket")
        return report
    report["bus"] = True
    system = _probe(context, "systemctl-state",
                    [hosts.TOOLS["systemctl"], "--user", "is-system-running"], env)
    answer = _text(system.stdout)
    report["system"] = answer if answer in SYSTEM_STATES else None
    unit = _probe(context, "systemctl-unit", [hosts.TOOLS["systemctl"], "--user", "show",
                                              "--property=LoadState", "--value", UNIT], env)
    report["units"][UNIT] = _text(unit.stdout) if unit.returncode == 0 else None
    if report["system"] is None or report["units"][UNIT] != "loaded":
        blockers.append(f"user-bus: systemctl --user did not answer for this user's units "
                        f"({UNIT}); see the private log")
    return report


def _toolchain(context, env, blockers):
    tools = {}
    for name, pattern in VERSIONS.items():
        path = hosts.TOOLS[name]
        real = os.path.realpath(path)
        entry = tools[name] = {"path": path, "real": real, "sha256": _file_sha256(real),
                               "version": None}
        try:
            result = _probe(context, f"{name}-version", [path, "--version"], env)
        except (Stop, OSError) as error:
            blockers.append(f"toolchain: {path} --version: {hosts._brief(error)}")
            continue
        text = _text(result.stdout)
        if result.returncode == 0 and re.fullmatch(pattern, text):
            entry["version"] = text
        else:
            blockers.append(f"toolchain: {path} --version gave no recognizable version")
    npm = tools["npm"]
    try:
        npm["package_version"] = json.loads(
            (Path(npm["real"]).parents[1] / "package.json").read_bytes()).get("version")
        with open(npm["real"], "rb") as stream:
            npm["shebang"] = _text(stream.readline(200))
    except (OSError, ValueError, AttributeError):
        npm["package_version"], npm["shebang"] = None, None
    if npm["version"] != NPM_VERSION or npm["package_version"] != NPM_VERSION:
        blockers.append(f"toolchain: {npm['path']} must be npm {NPM_VERSION}")
    return tools


def _overlaps(first, second):
    first, second = Path(first), Path(second)
    return first.is_relative_to(second) or second.is_relative_to(first)


def _caches(context, env, blockers):
    result = _probe(context, "npm-cache", [hosts.TOOLS["npm"], "config", "get", "cache"], env)
    prefixes = {"npm": _text(result.stdout) if result.returncode == 0 else None}
    prefixes.update({key: os.environ[key] for key in CACHE_KEYS if os.environ.get(key)})
    home = Path(context["home"])
    live = {path for name in LIVE for path in (str(home / name),
                                                 os.path.realpath(home / name))}
    for key, prefix in prefixes.items():
        if not prefix or not os.path.isabs(prefix):
            blockers.append(f"caches: the {key} cache prefix is not an absolute path")
        elif any(_overlaps(candidate, root) for candidate in
                 {os.path.normpath(prefix), os.path.realpath(prefix)} for root in live):
            blockers.append(f"caches: the {key} cache prefix overlaps live checkouts, "
                            "settings or state")
    return {"prefixes": prefixes, "python_bytecode": "disabled"}


def _git_auth(context, env, blockers):
    lock = Path(context["familiar"]) / "package-lock.json"
    try:
        resolved = json.loads(lock.read_bytes())["packages"]["node_modules/familiar-theme"][
            "resolved"]
    except (OSError, ValueError, KeyError, TypeError):
        blockers.append("git-auth: familiar's package-lock.json names no familiar-theme source")
        return None
    match = THEME_SOURCE.fullmatch(resolved) if isinstance(resolved, str) else None
    if match is None:
        blockers.append("git-auth: familiar-theme is not pinned to an SSH source and commit")
        return None
    report = {"source": match.group(1), "pin": match.group(2),
              "agent": "present" if os.environ.get("SSH_AUTH_SOCK") else "absent",
              "access": False}
    # The host's own Git and SSH configuration, with prompts off; no agent is required.
    git_env = {**env, "GIT_TERMINAL_PROMPT": "0", "SSH_ASKPASS_REQUIRE": "never"}
    try:
        result = _probe(context, "git-ls-remote",
                        [hosts.TOOLS["git"], "ls-remote", report["source"], "HEAD"], git_env)
        report["access"] = (result.returncode == 0
                            and LS_REMOTE.fullmatch(_text(result.stdout)) is not None)
    except (Stop, OSError):
        pass
    if not report["access"]:
        blockers.append("git-auth: the pinned familiar-theme source is not reachable "
                        "noninteractively with this host's Git and SSH setup; see the "
                        "private log")
    return report


def _helpers(context):
    hq, ops = Path(context["hq"]), Path(context["home"]) / "d/ops"
    package = hq / "tools/relay_cutover_bootstrap"
    members = {f"hq:{name}": _file_sha256(hq / name) for name in HELPERS}
    members.update({f"hq:tools/relay_cutover_bootstrap/{path.name}": _file_sha256(path)
                    for path in sorted(package.glob("*.py"))})
    members.update({f"ops:{name}": _file_sha256(ops / name) for name in EVIDENCE})
    return {"members": members,
            "package_sha256": hosts.helper_digest(package) if package.is_dir() else None}


def _resolve(link, family, pattern):
    real = os.path.realpath(link)
    base = os.path.realpath(family) + "/"
    try:
        info = os.stat(real)
    except OSError:
        info = None
    familiar = (info is not None and stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
                and os.access(real, os.X_OK) and real.startswith(base)
                and pattern.fullmatch(real[len(base):]) is not None)
    return {"path": str(link), "real": real, "familiar": familiar,
            "sha256": _file_sha256(real) if familiar else None}


def _claude_home(context, env, blockers, executable, name, directory):
    probe_env = hosts.claude_hold_env(env)
    probe_env.pop("CLAUDE_CONFIG_DIR", None)
    if not directory.is_dir():
        blockers.append(f"claude: the {name} home {directory} is missing")
        return None
    if name == "work":
        probe_env["CLAUDE_CONFIG_DIR"] = str(directory)
    report = {"home": str(directory), "hold": "DISABLE_UPDATES=1", "version": None,
              "doctor": None}
    try:
        version = _probe(context, f"claude-{name}-version", [executable, "--version"],
                         probe_env)
        text = _text(version.stdout)
        if version.returncode == 0 and CLAUDE_VERSION.fullmatch(text):
            report["version"] = text
        else:
            blockers.append(f"claude: {name} --version gave no recognizable version")
        doctor = _probe(context, f"claude-{name}-doctor", [executable, "doctor"], probe_env,
                        DOCTOR_SECONDS)
        held = (doctor.returncode == 0 and HOLD_DIAGNOSTIC in
                {line.strip() for line in _text(doctor.stdout).splitlines()})
        report["doctor"] = {"exit": doctor.returncode, "updates_disabled": held}
        if not held:
            blockers.append(f"claude: {name} doctor did not report \"{HOLD_DIAGNOSTIC}\"; "
                            "the recorded flag alone does not prove the hold")
    except (Stop, OSError) as error:
        blockers.append(f"claude: {name} probe: {hosts._brief(error)}")
    return report


def _harnesses(context, env, blockers):
    home = Path(context["home"])
    claude = _resolve(home / ".local/bin/claude", home / ".local/share/claude/versions",
                      CLAUDE_FAMILY)
    report = {"claude": claude}
    if not claude["familiar"]:
        blockers.append("claude: ~/.local/bin/claude does not resolve to a native Claude "
                        "version owned by this user; it was not run")
    else:
        claude["homes"] = {name: _claude_home(context, env, blockers, claude["path"], name,
                                              directory)
                           for name, directory in (("personal", home / ".claude"),
                                                   ("work", home / ".claude-work"))}
        versions = {entry["version"] for entry in claude["homes"].values() if entry}
        if len(versions) > 1:
            blockers.append("claude: the personal and work homes report different versions")
    if not hosts.HOSTS[context["host"]]["codex"]:
        return report
    codex = report["codex"] = _resolve(home / ".local/bin/codex",
                                       home / ".codex/packages/standalone/releases",
                                       CODEX_FAMILY)
    codex["homes"] = {name: (home / directory).is_dir()
                      for name, directory in (("personal", ".codex"), ("work", ".codex-work"))}
    codex["version"] = None
    if not codex["familiar"]:
        blockers.append("codex: ~/.local/bin/codex does not resolve to a standalone Codex "
                        "release owned by this user; it was not run")
        return report
    if not all(codex["homes"].values()):
        blockers.append("codex: the personal or work home is missing")
    probe_env = hosts.claude_hold_env(env)
    probe_env.pop("CODEX_HOME", None)
    try:
        result = _probe(context, "codex-version", [codex["path"], "--version"], probe_env)
        text = _text(result.stdout)
        if result.returncode == 0 and CODEX_VERSION.fullmatch(text):
            codex["version"] = text
        else:
            blockers.append("codex: --version gave no recognizable version")
    except (Stop, OSError) as error:
        blockers.append(f"codex: version probe: {hosts._brief(error)}")
    return report


def _preflight_checks(result, harness):
    out, err = _text(result.stdout).splitlines(), _text(result.stderr).splitlines()
    checks = {}
    for check in PREFLIGHT_CHECKS:
        prefix = f"relay-cutover: {check}: "
        if check == "evidence" and f"relay-cutover: evidence: {harness} absent" in out:
            checks[check] = "absent"
        elif any(line.startswith(prefix) for line in err):
            checks[check] = "failed"
        elif prefix + "ok" in out:
            checks[check] = "ok"
        else:
            checks[check] = "unknown"
    return checks


def _preflight(context, env, blockers, harnesses):
    """The existing helper's runtime, subscriber and evidence checks, as a bounded child."""
    home = Path(context["home"])
    # That helper finds claude and codex on PATH; list the fixed executables' directory
    # first so it checks the same binaries this inventory resolved and held.
    probe_env = hosts.claude_hold_env({**env, "PATH": f"{home / '.local/bin'}:{env['PATH']}"})
    for key in ("CLAUDE_CONFIG_DIR", "CODEX_HOME"):
        probe_env.pop(key, None)
    report = {}
    for harness, key in (("claude-code", "claude"), ("codex", "codex")):
        if key not in harnesses:
            continue
        if not harnesses[key]["familiar"]:
            report[harness] = "skipped"
            continue
        try:
            result = _probe(context, f"preflight-{harness}",
                            [hosts.TOOLS["python3"], "-B", Path(context["hq"]) / "tools/relay-cutover",
                             "preflight", "--harness", harness], probe_env, PREFLIGHT_SECONDS)
        except (Stop, OSError) as error:
            blockers.append(f"preflight: {harness}: {hosts._brief(error)}")
            continue
        checks = report[harness] = _preflight_checks(result, harness)
        for check in ("runtime", "subscribers", "evidence"):
            if checks[check] != "ok":
                blockers.append(f"preflight: {harness} {check} is {checks[check]}; see the "
                                "private log")
    return report


def _niri_config(home):
    """Startup commands from the niri config and the files it includes."""
    config = home / ".config/niri/config.kdl"
    files, commands = [config], []
    if config.is_file():
        for line in config.read_text(errors="replace").splitlines():
            match = INCLUDE.fullmatch(line)
            if match:
                name = match.group(1)
                path = home / name[2:] if name.startswith("~/") else config.parent / name
                files.append(path)
    for path in files:
        if path.is_file():
            for line in path.read_text(errors="replace").splitlines():
                match = SPAWN.fullmatch(line)
                if match:
                    commands.append(match.group(1).replace('\\"', '"').replace("\\\\", "\\"))
    return {name: [command for command in commands if marker in command]
            for name, marker in SURFACES.items()}


def _is_surface(name, row, home):
    argv = row["argv"]
    if name == "familiar-niri-watch":
        return f"{home}/d/familiar/bin/familiar-niri" in argv and argv[-1:] == ["watch"]
    return (bool(argv) and os.path.basename(argv[0]) == "qs"
            and f"{home}/d/familiar/integrations/niri-desktop" in argv)


def _niri_sockets(rows):
    """Sockets in this user's runtime directory named for a live niri compositor."""
    runtime = _runtime_dir()
    if runtime is None:
        return []
    niri = os.path.realpath(hosts.TOOLS["niri"])
    compositors = {row["pid"] for row in rows if row["comm"] == "niri" and row["exe"] == niri}
    trusted = []
    for entry in sorted(os.listdir(runtime)):
        match = NIRI_SOCKET.fullmatch(entry)
        path = os.path.join(runtime, entry)
        if match and int(match.group(1)) in compositors:
            info = os.lstat(path)
            if stat.S_ISSOCK(info.st_mode) and info.st_uid == os.getuid():
                trusted.append(path)
    return trusted


def _desktop(context, env, blockers, rows):
    home = Path(context["home"])
    reason = context["payload"].get("absence_reason")
    configured = _niri_config(home)
    running = {name: [{"pid": row["pid"], "start_time": row["start_time"], "argv": row["argv"]}
                      for row in rows if _is_surface(name, row, home)] for name in SURFACES}
    sockets = _niri_sockets(rows)
    report = {"state": None, "absence_reason": reason, "socket": None, "ipc": False,
              "surfaces": [{"name": name, "configured": configured[name],
                            "processes": running[name]} for name in SURFACES]}
    if not any(configured[name] or running[name] for name in SURFACES):
        if reason is None:
            report["state"] = "absent"
            blockers.append("desktop: no familiar surface is configured or running; record "
                            "an explained absence for this host or inspect it")
        else:
            report["state"] = "explained-absent"
            report["receipt"] = {"observed_at": hosts._now(), "surface_processes": 0,
                                 "configured_commands": 0, "trusted_sockets": len(sockets)}
        return report
    report["state"] = "present"
    if reason is not None:
        blockers.append("desktop: an absence reason was given but familiar surfaces are "
                        "configured or running")
    for name in SURFACES:
        if len(configured[name]) != 1:
            blockers.append(f"desktop: {name} has {len(configured[name])} startup commands "
                            "in the niri config; expected exactly one")
        if len(running[name]) != 1:
            blockers.append(f"desktop: {name} has {len(running[name])} running processes; "
                            "expected exactly one")
    if not sockets:
        blockers.append("desktop: no trusted niri socket for this user's session")
    elif len(sockets) > 1:
        blockers.append(f"desktop: {len(sockets)} trusted niri sockets make the desktop "
                        "context ambiguous")
    else:
        report["socket"] = sockets[0]
        try:
            result = _probe(context, "niri-ipc", [hosts.TOOLS["niri"], "msg", "--json", "version"],
                            {**env, "NIRI_SOCKET": sockets[0]}, 10)
            report["ipc"] = (result.returncode == 0
                             and isinstance(json.loads(result.stdout or b"null"), dict))
        except (Stop, OSError, ValueError):
            report["ipc"] = False
        if not report["ipc"]:
            blockers.append("desktop: read-only niri IPC on the trusted socket failed")
    return report


def _processes(context, rows, harnesses):
    """Known, unknown and unheld harness processes. Reported only, never refused here."""
    home = Path(context["home"])
    families = {"claude": os.path.realpath(home / ".local/share/claude/versions") + "/",
                "codex": os.path.realpath(home / ".codex/packages/standalone/releases") + "/"}
    expected = {name: harness["real"] for name, harness in harnesses.items()
                if harness["familiar"]}
    report = {"known": [], "unknown": [], "unheld": []}
    for row in rows:
        exe = row["exe"] or ""
        harness = next((name for name, family in families.items()
                        if row["comm"] == name or exe.startswith(family)), None)
        if harness is None:
            continue
        entry = {"pid": row["pid"], "start_time": row["start_time"], "harness": harness,
                 "exe": row["exe"]}
        if harness == "claude":
            entry["held"] = _hold(row["pid"])
            if entry["held"] is not True:
                report["unheld"].append(row["pid"])
        known = expected.get(harness) is not None and exe == expected[harness]
        report["known" if known else "unknown"].append(entry)
    return report


def _section(blockers, name, function, *args):
    try:
        return function(*args)
    except (Stop, OSError, ValueError) as error:
        blockers.append(f"{name}: {hosts._brief(error)}")
        return None


def inventory(context: dict) -> dict:
    """Read-only observation of this host for the cutover, run by `execute`, whose
    operation context supplies the payload, deadline and owned-child record.

    Records identity, the child PATH, the user bus, the system toolchain and caches, Git
    access to familiar-theme's pin, helper bytes, held Claude/Codex probes in both homes,
    the existing relay preflight, the desktop context and harness processes. `blockers`
    names unmet prerequisites; processes are reported, never blockers, because only the
    bootstrap and validation phases require closure and the hold."""
    blockers = []
    env = hosts._child_env(context)
    remainder, rejected = hosts._child_path(os.environ.get("PATH", ""))
    if rejected:
        blockers.append(f"environment: PATH has {rejected} empty or relative entries")
    report = {"host": context["host"], "observed_at": hosts._now(),
              "identity": _identity(context, blockers),
              "path": {"child": env["PATH"]},
              "user_bus": _section(blockers, "user-bus", _user_bus, context, env, blockers),
              "toolchain": _section(blockers, "toolchain", _toolchain, context, env, blockers),
              "caches": _section(blockers, "caches", _caches, context, env, blockers),
              "git_auth": _section(blockers, "git-auth", _git_auth, context, env, blockers),
              "helpers": _section(blockers, "helpers", _helpers, context)}
    harnesses = _section(blockers, "harnesses", _harnesses, context, env, blockers) or {}
    report["harnesses"] = harnesses
    report["preflight"] = _section(blockers, "preflight", _preflight, context, env, blockers,
                                   harnesses)
    rows = _process_rows()
    report["desktop"] = _section(blockers, "desktop", _desktop, context, env, blockers, rows)
    report["processes"] = _processes(context, rows, harnesses)
    report["blockers"] = blockers
    return report


OPERATIONS = {
    "inventory": hosts.Operation(run=inventory, deadline=INVENTORY_SECONDS, mutation=False,
                                 payload={"absence_reason": hosts._text_field(500)}),
}
