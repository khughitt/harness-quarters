"""The events a turn-pause hook feeds to the counters."""
from .record import Frozen

# agent_close closes the agent's open calls except those of tool `tool`.
# Kind: 'prompt', 'tool_start', 'tool_end', 'agent_stop', 'agent_close', 'compact', 'spawn', 'tick'.
KINDS = ('prompt', 'tool_start', 'tool_end', 'agent_stop', 'agent_close', 'compact', 'spawn', 'tick')

USER_WAIT_TOOLS = {'AskUserQuestion', 'request_user_input', 'request_user_input_async'}


class Event(Frozen):
    """One hook event; agent=None is the root, key identifies a spawn for deduplication."""
    __slots__ = _fields = ('t', 'agent', 'kind', 'call_id', 'tool', 'key')
    _defaults = {'call_id': None, 'tool': None, 'key': None}
