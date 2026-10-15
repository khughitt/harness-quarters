"""Project names for session cwds, read through `tasks resolve`, never from the registry."""
import json
import os
import shutil
import subprocess
from dataclasses import dataclass

from . import color


class ProjectError(Exception):
    """`tasks resolve` is missing or answered something unexpected; listing stops."""


@dataclass(frozen=True)
class Place:
    prefix: str
    worktree: str | None   # the worktree's directory name, None in the main checkout
    relpath: str           # below the checkout or worktree; "" at its top
    colour: color.Colour | None   # the project's, None when it has none


def sendable(path: str) -> bool:
    """One UTF-8 line on tasks' stdin: no line break, no lone surrogate (from a \\udcXX
    escape in a history line)."""
    if "\n" in path or "\r" in path:
        return False
    try:
        path.encode()
    except UnicodeEncodeError:
        return False
    return True


def resolve(cwds: list[str]) -> tuple[dict[str, Place | None], int]:
    """Each cwd's project, or None for its path to show instead, with one `tasks resolve
    --stdin` call for all of them; and how many cwds tasks could not resolve.

    None covers a cwd outside every project, one that two projects' former locations
    claim (`ambiguous`), and one tasks cannot read (`invalid`: permission denied, a stale
    mount) or that cannot travel as one line; the last two are counted. A failed call or an
    answer outside the contract stops the listing."""
    places: dict[str, Place | None] = {cwd: None for cwd in cwds if not sendable(cwd)}
    unresolved = len(places)
    asked = [cwd for cwd in cwds if cwd not in places]
    if not asked:
        return places, unresolved
    tasks = shutil.which("tasks")
    if tasks is None:
        raise ProjectError("tasks is not on PATH; project names come from `tasks resolve`")
    result = subprocess.run([tasks, "resolve", "--stdin"], input="".join(f"{cwd}\n" for cwd in asked),
                            capture_output=True, encoding="utf-8")
    if result.returncode != 0:
        raise ProjectError(f"tasks resolve exited {result.returncode}: {result.stderr.strip()}")
    try:
        rows = json.loads(result.stdout)["results"]
        if len(rows) != len(asked):
            raise ProjectError(f"tasks resolve answered {len(rows)} rows for {len(asked)} paths")
        for cwd, row in zip(asked, rows):
            if row["kind"] != "path":
                raise ProjectError(f"tasks resolve: {cwd}: read as {row['kind']!r}, not a path")
            if row["status"] == "resolved":
                places[cwd] = place(row)
            elif row["status"] in ("unregistered", "ambiguous", "invalid"):
                places[cwd] = None
                unresolved += row["status"] == "invalid"
            else:
                raise ProjectError(f"tasks resolve: {cwd}: unknown status {row['status']!r}")
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise ProjectError(f"tasks resolve: unexpected output ({error!r})") from None
    return places, unresolved


def place(row: dict) -> Place:
    """A storage match without a worktree is the storage directory itself (`.worktrees`)."""
    colour = None
    if "color" in row:
        try:
            colour = color.project_colour(row["color"])
        except ValueError as error:
            raise ProjectError(f"tasks resolve: {row['prefix']}: color {error}") from None
    worktree = row.get("worktree")
    if worktree:
        return Place(row["prefix"], os.path.basename(worktree), row["relpath"], colour)
    if row["via"] in ("storage", "former_storage"):
        if row["relpath"]:
            raise ProjectError(f"tasks resolve: {row['location']}: a storage match with relpath "
                               f"{row['relpath']!r} but no worktree")
        return Place(row["prefix"], None, os.path.basename(row["location"]), colour)
    return Place(row["prefix"], None, row["relpath"], colour)
