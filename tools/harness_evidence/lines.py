"""Physical lines, refs, format detection and lenient unescaping for the session-logs
reader. The lowest layer: it reads bytes and never writes."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Iterator


class UnknownFormat(Exception):
    pass


@dataclass(frozen=True)
class Place:
    harness: str
    home: str
    profile: str | None
    store: str
    relpath: str
    path: Path
    read_path: Path | None = None


@dataclass(frozen=True)
class Line:
    number: int
    raw: bytes
    complete: bool
    digest: str | None = None


def ref(place: Place, line: int | None = None, block: int | None = None) -> str:
    """`<home>:<relpath>#L<line>[#<block>]`; `file:<relpath>` for an explicit file."""
    home = "file" if place.store == "explicit" else place.home
    if block is not None and line is None:
        raise ValueError("a block ref needs a line")
    out = f"{home}:{place.relpath}"
    if line is not None:
        out += f"#L{line}"
        if block is not None:
            out += f"#{block}"
    return out


def lines(path: Path, size: int) -> Iterator[Line]:
    """Every physical line in the first `size` bytes, blank ones included, read one line
    at a time. Only a last line without a newline (or cut by the bound) is incomplete."""
    remaining = size
    number = 0
    with path.open("rb") as handle:
        while remaining > 0:
            raw = handle.readline(remaining)
            if not raw:
                return
            remaining -= len(raw)
            number += 1
            yield Line(number, raw, raw.endswith(b"\n"))


def sha256(line: Line) -> str:
    return line.digest if line.digest is not None else hashlib.sha256(line.raw).hexdigest()


def decode(line: Line) -> dict | None:
    """The line as a JSON object, or None. Invalid UTF-8 is replaced, not rejected."""
    try:
        value = json.loads(line.raw.decode("utf-8", errors="replace"))
    except (ValueError, RecursionError):
        return None
    return value if isinstance(value, dict) else None


_ESCAPE = re.compile(
    r'\\u([dD][89abAB][0-9a-fA-F]{2})\\u([dD][c-fC-F][0-9a-fA-F]{2})'
    r'|\\(u[0-9a-fA-F]{4}|["\\/bfnrt])')
_SIMPLE = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}


def unescape_lenient(text: str) -> str:
    """Undo JSON string escapes where they are well formed and leave the rest as is."""
    def one(match: re.Match) -> str:
        if match.group(1):
            high, low = int(match.group(1), 16), int(match.group(2), 16)
            return chr(0x10000 + ((high - 0xD800) << 10) + (low - 0xDC00))
        body = match.group(3)
        if body[0] != "u":
            return _SIMPLE[body]
        code = int(body[1:], 16)
        # An unpaired surrogate cannot be encoded: leave it as written.
        return match.group(0) if 0xD800 <= code <= 0xDFFF else chr(code)
    return _ESCAPE.sub(one, text)


# Claude record kinds that come without a sessionId: a closed set observed in real
# transcripts. Extend it here when a new sessionId-less kind appears.
_CLAUDE_KINDS = frozenset({
    "fork-context-ref", "summary", "file-history-snapshot", "queue-operation",
    "custom-title", "ai-title", "last-prompt", "permission-mode", "pr-link", "agent-name",
})
_SDK_TYPES = frozenset({"system", "user", "assistant", "result"})


def _signature(record: dict) -> str | None:
    if record.get("type") == "session_meta":
        return "codex"
    if "sessionId" in record or record.get("type") in _CLAUDE_KINDS:
        return "claude"
    if "session_id" in record and record.get("type") in _SDK_TYPES:
        return "sdk"
    return None


def detect_format(path: Path, size: int) -> str:
    """The first record that matches a signature decides; other lines are skipped."""
    for line in lines(path, size):
        record = decode(line)
        found = _signature(record) if record is not None else None
        if found:
            return found
    raise UnknownFormat(f"no record in {path} matches a known format")
