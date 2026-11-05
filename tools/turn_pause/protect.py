"""The protected-path check every PreToolUse runs, and the structure bound that keeps it
inside the hook's time budget. Kept apart from the allowlist so the hook loads the
allowlist (with shlex) only once a turn is paused.

The bound is on JSON nodes, not bytes: a payload just under the byte cap made of tiny
elements (`[0,0,...]`, `[[],[],...]`) has some sixteen million nodes, and parsing and
walking them took the entry over five seconds, past the hook timeout, which lets the call
through. No real tool input has millions of nodes, so past MAX_NODES the call is refused,
paused or not. `too_many_nodes` bounds the raw bytes before json.loads; `_strings` bounds
a parsed value (the hook's decide is also called with dicts).
"""
from __future__ import annotations

import os

MAX_NODES = 2_000_000


class TooManyNodes(ValueError):
    """A tool input with more than MAX_NODES JSON nodes."""


def too_many_nodes(raw: bytes) -> bool:
    """Whether the JSON text has more than MAX_NODES nodes, decided before parsing it.
    Each value after the first in a container follows a comma and each container opens
    with a bracket, so nodes <= 2 * (commas + openers) + 1 counting object keys. The
    first count includes commas inside strings, so when it is over the budget the strings
    themselves are counted (each is a node) and then, if still unsettled, the separators
    outside strings exactly. Every step is a C-speed pass over the bytes. The count is an
    upper bound, so an input with between MAX_NODES / 2 and MAX_NODES nodes may also be
    refused; an input under a million nodes never is."""
    tokens = raw.count(b',') + raw.count(b'[') + raw.count(b'{')
    if 2 * tokens + 1 <= MAX_NODES:
        return False
    if (raw.count(b'"') - raw.count(b'\\"')) // 2 > MAX_NODES:
        return True
    parts = raw.replace(b'\\\\', b'').replace(b'\\"', b'').split(b'"')
    outside = b''.join(parts[::2])
    tokens = outside.count(b',') + outside.count(b'[') + outside.count(b'{')
    return 2 * tokens + 1 > MAX_NODES


def touches_protected(tool_input: dict, paths: Sequence[Path]) -> bool:
    """Whether any string in the input names a protected path, in full or with ~.
    A string match: it raises the bar, it is not a sandbox. Raises TooManyNodes past
    MAX_NODES."""
    # One search per needle over all strings joined by NUL, which no path contains, so a
    # match never spans two strings: linear, and fast on multi-megabyte inputs.
    text = '\0'.join(_strings(tool_input))
    if not text or (os.sep not in text and '~' not in text and all(os.sep in str(p) for p in paths)):
        return False
    home = os.path.expanduser('~')
    needles = set()
    for path in paths:
        full = os.path.expanduser(str(path))
        for form in {full, os.path.realpath(full)}:
            needles.add(form)
            if form.startswith(home + os.sep):
                needles.add('~' + form[len(home):])
    return any(needle in text for needle in needles)


def _strings(value) -> Iterator[str]:
    """Every string in a JSON value, keys included; iterative, so no depth escapes.
    Raises TooManyNodes once more than MAX_NODES nodes have been visited."""
    stack = [value]
    seen = 0
    while stack:
        item = stack.pop()
        seen += 1
        if seen > MAX_NODES:
            raise TooManyNodes(f'the tool input has more than {MAX_NODES} JSON nodes')
        if isinstance(item, str):
            yield item
        elif isinstance(item, dict):
            stack.extend(item.keys())
            stack.extend(item.values())
        elif isinstance(item, (list, tuple)):
            stack.extend(item)
