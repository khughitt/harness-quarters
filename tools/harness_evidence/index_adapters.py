"""Index adapters keyed by harness slug; a harness without an entry has no index path."""
from types import ModuleType

from . import index_claude
from ._protocol import ProtocolError

ADAPTERS: dict[str, ModuleType] = {"claude-code": index_claude}


def adapter(harness: str) -> ModuleType:
    """The registered adapter for `harness`, or a protocol error naming it."""
    try:
        return ADAPTERS[harness]
    except KeyError:
        raise ProtocolError(f"no index adapter for {harness}") from None
