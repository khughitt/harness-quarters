"""Tell the user a turn paused: a desktop notification and a relay inbox notice.

notify-send starts detached with every standard stream redirected, so nothing holds the
hook open. The relay notice is one `notify` request on relay serve's private socket
(relay docs/api.md, "Local socket protocol"; the notice shape under "Messages and
entries"), bounded by a 300 ms timeout. relay serve not running (no socket, or nobody
listening on it) is not a failure: the spec sends the notice when serve is reachable.
The heavy imports are local to send(), which runs only when a pause fires.
"""
from __future__ import annotations

import os
import time

TIMEOUT = 0.3
NOTICE_TTL_MS = 24 * 3600 * 1000
TITLE_MAX = 80
TEXT_MAX = 2000


def relay_socket(env: Mapping[str, str]) -> str:
    base = env.get('XDG_STATE_HOME') or os.path.join(env['HOME'], '.local', 'state')
    return os.path.join(base, 'relay', 'serve.sock')


def notice(title: str, body: str, *, agent: str | None, cwd: str | None, now_ms: int, id_: str) -> dict:
    """A relay notice message (schema 1): from the agent when named, to the user."""
    return {
        'schema': 1, 'id': id_, 'kind': 'notice', 'correlationId': id_,
        'from': {'kind': 'agent', 'agentId': agent} if agent else {'kind': 'user'},
        'to': {'kind': 'user'},
        'createdAt': now_ms,
        'context': {'project': None, 'taskId': None, 'cwd': cwd},
        'body': {'expiresAt': now_ms + NOTICE_TTL_MS, 'title': (title or 'turn paused')[:TITLE_MAX],
                 'text': body[:TEXT_MAX], 'level': 'warn'},
    }


def _desktop(title: str, body: str, env: Mapping[str, str]) -> str | None:
    import subprocess
    try:
        subprocess.Popen(['notify-send', '--app-name=turn-pause', '--urgency=critical', title, body],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         env=dict(env), start_new_session=True, close_fds=True)
    except OSError as e:
        return f'notify-send: {e}'
    return None


def _relay(title: str, body: str, env: Mapping[str, str], agent: str | None, cwd: str | None) -> str | None:
    import json
    import socket
    import uuid
    deadline = time.monotonic() + TIMEOUT

    def left() -> float:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        return remaining

    path = relay_socket(env)
    req_id = str(uuid.uuid4())
    message = notice(title, body, agent=agent, cwd=cwd, now_ms=int(time.time() * 1000), id_=str(uuid.uuid4()))
    line = (json.dumps({'reqId': req_id, 'op': 'notify', 'message': message}) + '\n').encode()
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.settimeout(left())
        try:
            sock.connect(path)
        except (FileNotFoundError, ConnectionRefusedError):
            return None
        sock.settimeout(left())
        sock.sendall(line)
        buf = b''
        while True:
            while b'\n' not in buf:
                sock.settimeout(left())
                chunk = sock.recv(65536)
                if not chunk:
                    return f'relay: {path} closed the connection before replying'
                buf += chunk
            first, buf = buf.split(b'\n', 1)
            reply = json.loads(first)
            if not isinstance(reply, dict) or reply.get('reqId') != req_id:
                continue
            if reply.get('ok') is True:
                return None
            error = reply.get('error') if isinstance(reply.get('error'), dict) else {}
            return f"relay: notify refused: {error.get('code')}: {error.get('message')}"
    except (TimeoutError, socket.timeout):
        return f'relay: no reply from {path} within {int(TIMEOUT * 1000)} ms (timed out)'
    except ValueError as e:
        return f'relay: unreadable reply from {path}: {e}'
    except OSError as e:
        return f'relay: {path}: {e}'
    finally:
        sock.close()


def send(title: str, body: str, *, env: Mapping[str, str], agent: str | None = None,
         cwd: str | None = None) -> str | None:
    """Start notify-send, then write one relay notice; both are tried. The first error, or None."""
    errors = [e for e in (_desktop(title, body, env), _relay(title, body, env, agent, cwd)) if e]
    return errors[0] if errors else None
