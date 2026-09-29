#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["rich>=13", "pyyaml>=6", "click>=8"]
# ///
"""List installed skills sorted by description length.

Only the frontmatter `description` is loaded into context at session start,
so its length is the per-skill cost of having the skill available.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import click
import yaml
from rich.console import Console
from rich.table import Table

USER_SKILLS = Path.home() / ".agents" / "skills"
PLUGIN_CACHE = Path.home() / ".claude" / "plugins" / "cache"


@dataclass
class Skill:
    name: str
    source: str
    description: str
    path: Path

    @property
    def desc_len(self) -> int:
        return len(self.description)


def parse_frontmatter(path: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    try:
        _, fm, _ = text.split("---", 2)
    except ValueError:
        return None
    try:
        data = yaml.safe_load(fm)
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def collect_user_skills(root: Path, source_label: str = "user") -> Iterable[Skill]:
    if not root.is_dir():
        return
    for skill_md in sorted(root.glob("*/SKILL.md")):
        fm = parse_frontmatter(skill_md)
        if not fm:
            continue
        yield Skill(
            name=str(fm.get("name") or skill_md.parent.name),
            source=source_label,
            description=str(fm.get("description") or "").strip(),
            path=skill_md,
        )


def collect_plugin_skills(root: Path) -> Iterable[Skill]:
    """Plugin skills live under cache/<marketplace>/<plugin>/<version>/skills/<name>/SKILL.md.

    Skills are exposed to the model as `plugin:<skill-name>`, so prefix the name accordingly.
    Only the highest-version copy per (plugin, skill) is reported to avoid double-counting
    when multiple versions are cached.
    """
    if not root.is_dir():
        return
    # key: (plugin, skill_name) -> (version_tuple, Skill)
    latest: dict[tuple[str, str], tuple[tuple[int, ...], Skill]] = {}
    for skill_md in root.glob("*/*/*/skills/*/SKILL.md"):
        # parts: .../cache/<marketplace>/<plugin>/<version>/skills/<name>/SKILL.md
        parts = skill_md.relative_to(root).parts
        if len(parts) < 6:
            continue
        plugin, version, skill_name = parts[1], parts[2], parts[4]
        fm = parse_frontmatter(skill_md)
        if not fm:
            continue
        version_key = tuple(int(p) if p.isdigit() else 0 for p in version.split("."))
        key = (plugin, skill_name)
        skill = Skill(
            name=f"{plugin}:{fm.get('name') or skill_name}",
            source=f"plugin:{plugin}",
            description=str(fm.get("description") or "").strip(),
            path=skill_md,
        )
        prev = latest.get(key)
        if prev is None or version_key > prev[0]:
            latest[key] = (version_key, skill)
    for _, skill in latest.values():
        yield skill


@click.command()
@click.option(
    "--source",
    type=click.Choice(["all", "user", "plugin"]),
    default="all",
    help="Filter built-in sources (user = ~/.agents/skills, plugin = ~/.claude/plugins cache).",
)
@click.option(
    "--dir",
    "extra_dirs",
    multiple=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Additional skills root (expects <dir>/<skill>/SKILL.md layout). Repeatable.",
)
@click.option("--min-length", type=int, default=0, help="Only show skills with description >= N chars.")
@click.option("--limit", type=int, default=None, help="Show only the top N longest.")
def main(source: str, extra_dirs: tuple[Path, ...], min_length: int, limit: int | None) -> None:
    skills: list[Skill] = []
    if source in ("all", "user"):
        skills.extend(collect_user_skills(USER_SKILLS, source_label="user"))
    if source in ("all", "plugin"):
        skills.extend(collect_plugin_skills(PLUGIN_CACHE))
    for d in extra_dirs:
        skills.extend(collect_user_skills(d.resolve(), source_label=f"dir:{d.name}"))

    skills = [s for s in skills if s.desc_len >= min_length]
    skills.sort(key=lambda s: s.desc_len, reverse=True)
    if limit is not None:
        skills = skills[:limit]

    console = Console()
    table = Table(title=f"Skill description sizes ({len(skills)} skills)", show_lines=False)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Chars", justify="right", style="cyan")
    table.add_column("Words", justify="right", style="cyan")
    table.add_column("Skill", style="bold")
    table.add_column("Source", style="magenta")

    total_chars = 0
    total_words = 0
    for i, s in enumerate(skills, 1):
        words = len(s.description.split())
        total_chars += s.desc_len
        total_words += words
        table.add_row(str(i), f"{s.desc_len:,}", f"{words:,}", s.name, s.source)

    console.print(table)
    console.print(
        f"[bold]Total:[/bold] {total_chars:,} chars, {total_words:,} words "
        f"across {len(skills)} skill{'s' if len(skills) != 1 else ''}"
    )


if __name__ == "__main__":
    main()
