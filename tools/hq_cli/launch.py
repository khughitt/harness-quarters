"""Resume a session in its own harness, home and recorded cwd, or refuse."""
import os
import sys
import tomllib
from pathlib import Path

from .sessions import Session

HOME_VARIABLES = {"claude": "CLAUDE_CONFIG_DIR", "codex": "CODEX_HOME"}


class LaunchError(Exception):
    """The session cannot be resumed where it ran; nothing is launched."""


def load_flags(path: Path) -> dict[str, list[str]]:
    try:
        data = tomllib.loads(path.read_text())
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise LaunchError(f"{path}: cannot read launch flags: {error}") from None
    table = data.get("homes")
    if not isinstance(table, dict):
        raise LaunchError(f"{path}: missing [homes.<home>] tables")
    flags = {}
    for home, entry in table.items():
        value = entry.get("flags") if isinstance(entry, dict) else None
        if not (isinstance(value, list) and all(isinstance(flag, str) for flag in value)):
            raise LaunchError(f"{path}: homes.{home}.flags must be a list of strings")
        flags[home] = value
    return flags


def argv(session: Session, flags: list[str]) -> list[str]:
    if session.home.harness == "claude":
        return ["claude", *flags, "--resume", session.id]
    return ["codex", *flags, "resume", session.id]   # Codex takes its flags before the subcommand


def environment(session: Session, base: dict[str, str]) -> dict[str, str]:
    """A work row names its home; a personal row unsets both variables, since setting
    CLAUDE_CONFIG_DIR=~/.claude would read a different .claude.json than ~/.claude.json."""
    env = dict(base)
    if session.home.kind == "work":
        env[HOME_VARIABLES[session.home.harness]] = str(session.home.path)
    else:
        for variable in HOME_VARIABLES.values():
            env.pop(variable, None)
    return env


def launch(session: Session, flags_by_home: dict[str, list[str]], config: Path) -> None:
    """Replace this process with the harness; rechecks cwd and transcript just before."""
    if session.home.name not in flags_by_home:
        raise LaunchError(f"{config}: no [homes.{session.home.name}] flags; add them to launch this home")
    if not os.path.isdir(session.cwd):
        raise LaunchError(f"cwd missing: {session.cwd}; not launching elsewhere")
    if not session.transcript.is_file():
        raise LaunchError(f"transcript gone: {session.transcript}")
    command = argv(session, flags_by_home[session.home.name])
    env = environment(session, dict(os.environ))
    sys.stdout.flush()
    sys.stderr.flush()
    try:
        os.chdir(session.cwd)
        os.execvpe(command[0], command, env)
    except OSError as error:
        raise LaunchError(f"cannot run {command[0]} in {session.cwd}: {error}") from None
