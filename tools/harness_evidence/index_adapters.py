"""Index adapters keyed by harness slug; a harness without an entry has no index path."""
from types import ModuleType

from . import index_agy, index_claude
from ._protocol import ProtocolError

# agy's entry has no `extract` until its extractor lands; its header and facts are served.
ADAPTERS: dict[str, ModuleType] = {"claude-code": index_claude, "agy": index_agy}


def adapter(harness: str) -> ModuleType:
    """The registered adapter for `harness`, or a protocol error naming it."""
    try:
        return ADAPTERS[harness]
    except KeyError:
        raise ProtocolError(f"no index adapter for {harness}") from None


def for_source(place, *, extract: bool) -> ModuleType:
    """The adapter for one held source, refusing sources the adapter does not read."""
    module = adapter(place.harness)
    refused = module.refusal(place)
    if refused is not None:
        raise ProtocolError(refused)
    if extract and not hasattr(module, "extract"):
        raise ProtocolError(f"no index extractor for {place.harness}")
    return module
