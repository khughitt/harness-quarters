"""The events a turn-pause hook feeds to the counters."""
from dataclasses import dataclass
from typing import Literal

Kind = Literal['prompt', 'tool_start', 'tool_end', 'agent_stop', 'compact', 'spawn', 'tick']

USER_WAIT_TOOLS = {'AskUserQuestion', 'request_user_input', 'request_user_input_async'}


@dataclass(frozen=True)
class Event:
    """One hook event; agent=None is the root, key identifies a spawn for deduplication."""
    t: float
    agent: str | None
    kind: Kind
    call_id: str | None = None
    tool: str | None = None
    key: str | None = None
