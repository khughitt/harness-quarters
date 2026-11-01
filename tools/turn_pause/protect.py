"""The protected-path check every PreToolUse runs, kept apart from the allowlist so the
hook loads the allowlist (with shlex) only once a turn is paused."""
from __future__ import annotations

import os


def touches_protected(tool_input: dict, paths: Sequence[Path]) -> bool:
    """Whether any string in the input names a protected path, in full or with ~.
    A string match: it raises the bar, it is not a sandbox."""
    home = os.path.expanduser('~')
    needles = set()
    for path in paths:
        full = os.path.expanduser(str(path))
        for form in {full, os.path.realpath(full)}:
            needles.add(form)
            if form.startswith(home + os.sep):
                needles.add('~' + form[len(home):])
    # One search per needle over all strings joined by NUL, which no path contains, so a
    # match never spans two strings: linear, and fast on multi-megabyte inputs.
    text = '\0'.join(_strings(tool_input))
    return any(needle in text for needle in needles)


def _strings(value) -> Iterator[str]:
    """Every string in a JSON value, keys included; iterative, so no depth escapes."""
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            yield item
        elif isinstance(item, dict):
            stack.extend(item.keys())
            stack.extend(item.values())
        elif isinstance(item, (list, tuple)):
            stack.extend(item)
