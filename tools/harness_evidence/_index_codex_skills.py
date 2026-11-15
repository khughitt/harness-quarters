"""Native skill-read convention relocated from OBS 1e0afad1.

Infer skill reads from Codex shell calls: extract each cmd value, then apply one rule."""

import json
import os
import re


READERS = {"cat", "sed", "head", "tail", "bat", "less"}
NAME = r"[A-Za-z0-9_][A-Za-z0-9_.-]*"
SKILL_PATH = re.compile(rf"^(?:[^=\s]*/)?skills/(?:{NAME}/)*({NAME})/SKILL\.md$")
COMMAND_SEPARATORS = {";", "|", "||", "&", "&&", "\n"}
REDIRECTIONS = {">", ">>", "<", "<<<", ">|", "&>", "&>>", ">&", "<&", "<>"}
OPERATOR_CHARS = ";|&<>"
UNSUPPORTED_SHELL = "()`"
COMPLETE, UNSUPPORTED, UNTERMINATED = "complete", "unsupported", "unterminated"
KEY = re.compile(r"""\s*(?:"([A-Za-z_][A-Za-z0-9_]*)"|'([A-Za-z_][A-Za-z0-9_]*)'|([A-Za-z_][A-Za-z0-9_]*))\s*:\s*""")
SCALAR = re.compile(r"\s*(?:-?\d+(?:\.\d+)?|true|false|null)\s*")
ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}
EXEC_CALL = "tools.exec_command("
JSON_CMD_KEYS = {"exec_command": "cmd", "shell_command": "command"}


# --- JavaScript side: the current Codex `exec` record wraps commands in a snippet -----

def _literal(text, start):
    """Decode the JS string literal opening at text[start]: (value, end) or None."""
    quote = text[start]
    out, i = [], start + 1
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 1
            if i >= len(text):
                return None
            esc = text[i]
            if esc == "u" and re.fullmatch(r"[0-9a-fA-F]{4}", text[i + 1:i + 5]):
                out.append(chr(int(text[i + 1:i + 5], 16)))
                i += 5
                continue
            out.append(ESCAPES.get(esc, esc))
            i += 1
            continue
        if ch == quote:
            return "".join(out), i + 1
        if quote == "`" and text.startswith("${", i):
            return None
        out.append(ch)
        i += 1
    return None


def _skip_string(text, start):
    """End of the JS string or template opening at text[start], escapes honoured; None if unterminated."""
    quote, i = text[start], start + 1
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch == quote:
            return i + 1
        i += 1
    return None


def _exec_cmd(text, start):
    """The cmd property of the object literal opening at text[start]: (value, end) or None."""
    i = start
    while True:
        key = KEY.match(text, i)
        if key is None:
            return None
        name = key.group(1) or key.group(2) or key.group(3)
        i = key.end()
        if i < len(text) and text[i] in "\"'`":
            literal = _literal(text, i)
            if literal is None:
                return None
            value, i = literal
        else:
            scalar = SCALAR.match(text, i)
            if scalar is None:
                return None
            value, i = None, scalar.end()
        tail = re.match(r"\s*([,}])", text[i:])
        if tail is None:
            return None
        i += tail.end()
        if name == "cmd":
            return value, i
        if tail.group(1) == "}":
            return None


def _exec_cmds(snippet):
    """Every plain cmd literal passed to tools.exec_command in code, not in strings or comments."""
    values, i, n = [], 0, len(snippet)
    while i < n:
        ch = snippet[i]
        if ch in "\"'`":
            end = _skip_string(snippet, i)
            if end is None:
                return values
            i = end
        elif snippet.startswith("//", i):
            end = snippet.find("\n", i)
            i = n if end < 0 else end + 1
        elif snippet.startswith("/*", i):
            end = snippet.find("*/", i + 2)
            i = n if end < 0 else end + 2
        elif snippet.startswith(EXEC_CALL, i):
            i += len(EXEC_CALL)
            brace = re.match(r"\s*\{", snippet[i:])
            if brace is None:
                continue
            found = _exec_cmd(snippet, i + brace.end())
            if found is None:
                i += brace.end()
                continue
            value, i = found
            if value is not None:
                values.append(value)
        else:
            i += 1
    return values


def cmd_values(tool, value):
    """Every plain-string cmd value in a Codex shell call; other tools yield nothing."""
    if not isinstance(value, str):
        return []
    if tool in JSON_CMD_KEYS:
        try:
            arguments = json.loads(value)
        except ValueError:
            return []
        cmd = arguments.get(JSON_CMD_KEYS[tool]) if isinstance(arguments, dict) else None
        return [cmd] if isinstance(cmd, str) else []
    if tool != "exec":
        return []
    return _exec_cmds(value)


# --- Shell side: POSIX words with quoting kept apart from operators ---------------------

def _words(cmd):
    """(text, is_operator) tokens up to the first unsupported construct.

    Everything from the simple command holding that construct onward is dropped: the
    tokens kept end at the last command separator before it, or are empty. An
    unterminated quote is a shell syntax error, so nothing ran and nothing is kept.
    """
    words = []
    outcome = _scan(cmd, words)
    if outcome == COMPLETE:
        return words
    if outcome == UNTERMINATED:
        return []
    kept = 0
    for i, (text, is_operator) in enumerate(words):
        if is_operator and text in COMMAND_SEPARATORS:
            kept = i + 1
    del words[kept:]
    return words


def _scan(cmd, words):
    """Append (text, is_operator) tokens to words; stops at the first unsupported construct."""
    buf, in_word, i, n = [], False, 0, len(cmd)

    def flush():
        nonlocal buf, in_word
        if in_word:
            words.append(("".join(buf), False))
        buf, in_word = [], False

    while i < n:
        ch = cmd[i]
        if ch in " \t\r":
            flush()
            i += 1
        elif ch == "\n":
            flush()
            words.append(("\n", True))
            i += 1
        elif ch == "#" and not in_word:
            end = cmd.find("\n", i)
            i = n if end < 0 else end
        elif ch in OPERATOR_CHARS:
            flush()
            j = i
            while j < n and cmd[j] in OPERATOR_CHARS:
                j += 1
            operator = cmd[i:j]
            if operator not in COMMAND_SEPARATORS and operator not in REDIRECTIONS:
                return UNSUPPORTED
            words.append((operator, True))
            i = j
        elif ch in UNSUPPORTED_SHELL:
            return UNSUPPORTED
        elif ch == "\\":
            if i + 1 >= n:
                return UNSUPPORTED
            if cmd[i + 1] != "\n":
                buf.append(cmd[i + 1])
                in_word = True
            i += 2
        elif ch == "'":
            end = cmd.find("'", i + 1)
            if end < 0:
                return UNTERMINATED
            buf.append(cmd[i + 1:end])
            in_word = True
            i = end + 1
        elif ch == '"':
            i += 1
            in_word = True
            while True:
                if i >= n:
                    return UNTERMINATED
                ch = cmd[i]
                if ch == '"':
                    i += 1
                    break
                if ch == "\\" and i + 1 < n and cmd[i + 1] in '"\\$`\n':
                    if cmd[i + 1] != "\n":
                        buf.append(cmd[i + 1])
                    i += 2
                    continue
                buf.append(ch)
                i += 1
        else:
            buf.append(ch)
            in_word = True
            i += 1
    flush()
    return COMPLETE


def _simple_commands(cmd):
    """Operand lists per simple command; an input redirection's target is an operand, others are dropped."""
    commands, current, redirect = [], [], None
    for text, is_operator in _words(cmd):
        if redirect is not None:
            if redirect == "<":
                current.append(text)
            redirect = None
        elif is_operator and text in COMMAND_SEPARATORS:
            commands.append(current)
            current = []
        elif is_operator:
            redirect = text
        else:
            current.append(text)
    commands.append(current)
    return commands


SED_ARGUMENT_OPTIONS = "efl"


def _in_place(operands):
    """True when a sed operand list carries -i / --in-place: an edit, not a read."""
    for operand in operands:
        if operand == "--in-place" or operand.startswith("--in-place="):
            return True
        if operand.startswith("-") and not operand.startswith("--"):
            for flag in operand[1:]:
                if flag == "i":
                    return True
                if flag in SED_ARGUMENT_OPTIONS:
                    break
    return False


def read_skills(cmd):
    """Skill names read by cat/sed/head/tail/bat/less as a file operand in any simple command."""
    names = set()
    for operands in _simple_commands(cmd):
        if not operands:
            continue
        reader = os.path.basename(operands[0])
        if reader not in READERS or (reader == "sed" and _in_place(operands[1:])):
            continue
        for operand in operands[1:]:
            match = SKILL_PATH.match(operand)
            if match:
                names.add(match.group(1))
    return sorted(names)


def from_call(tool, value):
    """Distinct skill names read by one Codex tool call, sorted."""
    names = set()
    for cmd in cmd_values(tool, value):
        names.update(read_skills(cmd))
    return sorted(names)
