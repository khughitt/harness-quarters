"""Prompt rules: which prompts start a turn, what the user typed, and the budget directive."""
import re

from .record import Frozen

PASTED_OPEN = '<pasted_content'
_PASTED_BLOCK = re.compile(r'<pasted_content id="([^"]*)">.*?</pasted_content id="\1">', re.DOTALL)
_DURATION = re.compile(r'([0-9]{1,6}(?:\.[0-9]{1,6})?)([hm])')
_COUNT = re.compile(r'([0-9]{1,9}) (calls|agents|compactions)')
_UNIT_SECONDS = {'h': 3600, 'm': 60}
_COUNT_FIELD = {'calls': 'calls', 'agents': 'agents', 'compactions': 'compactions'}


class Budget(Frozen):
    __slots__ = _fields = ('seconds', 'calls', 'agents', 'compactions')


class Malformed(Frozen):
    __slots__ = _fields = ('reason',)


def is_genuine(text: str, harness: str) -> bool:
    """True when the prompt is human text, not an injected block."""
    stripped = text.strip()
    if not stripped:
        return False
    if stripped.startswith('<') and not stripped.startswith(PASTED_OPEN):
        return False
    if harness == 'codex' and stripped.startswith('# AGENTS.md'):
        return False
    return True


def typed_text(text: str) -> str:
    """The text with every pasted_content block removed."""
    return _PASTED_BLOCK.sub('', text)


def parse_budget(text: str) -> Budget | Malformed | None:
    """The budget directive on the first non-empty typed line, if any."""
    first = next((line.strip() for line in typed_text(text).splitlines() if line.strip()), '')
    if not first.lower().startswith('budget:'):
        return None
    parts = [part.strip() for part in first[len('budget:'):].split(',')]
    match = _DURATION.fullmatch(parts[0])
    if not match:
        return Malformed(f'duration {parts[0]!r} is not like 12h, 90m or 1.5h')
    seconds = round(float(match.group(1)) * _UNIT_SECONDS[match.group(2)])
    if seconds <= 0:
        return Malformed('duration must be above zero')
    counts: dict[str, int] = {}
    for part in parts[1:]:
        count = _COUNT.fullmatch(part)
        if not count:
            return Malformed(f'{part!r} is not like "2000 calls", "80 agents" or "3 compactions"')
        if int(count.group(1)) == 0:
            return Malformed(f'{part!r}: a count must be above zero')
        name = _COUNT_FIELD[count.group(2)]
        if name in counts:
            return Malformed(f'{count.group(2)} named twice')
        counts[name] = int(count.group(1))
    return Budget(seconds, counts.get('calls'), counts.get('agents'), counts.get('compactions'))
