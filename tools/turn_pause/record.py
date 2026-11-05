"""Plain records: __slots__ classes with field-wise construction, equality and repr.

They stand in for dataclasses in every module the hook imports: importing dataclasses
(with inspect) cost the hook about 18 ms a call, more than its own work. A subclass
names its fields in `_fields` (also its `__slots__`), defaults in `_defaults`, and
mutable defaults as factories in `_factories`.
"""


class Record:
    __slots__ = ()
    _fields: tuple = ()
    _defaults: dict = {}
    _factories: dict = {}

    def __init__(self, *args, **kwargs):
        name = type(self).__name__
        if len(args) > len(self._fields):
            raise TypeError(f'{name}() takes {len(self._fields)} arguments, {len(args)} given')
        values = dict(zip(self._fields, args))
        for key, value in kwargs.items():
            if key not in self._fields:
                raise TypeError(f'{name}() got an unexpected keyword argument {key!r}')
            if key in values:
                raise TypeError(f'{name}() got multiple values for {key!r}')
            values[key] = value
        for field in self._fields:
            if field in values:
                value = values[field]
            elif field in self._factories:
                value = self._factories[field]()
            elif field in self._defaults:
                value = self._defaults[field]
            else:
                raise TypeError(f'{name}() missing required argument {field!r}')
            object.__setattr__(self, field, value)

    def _astuple(self) -> tuple:
        return tuple(getattr(self, f) for f in self._fields)

    def _asdict(self) -> dict:
        return {f: getattr(self, f) for f in self._fields}

    def __eq__(self, other):
        if type(other) is not type(self):
            return NotImplemented
        return self._astuple() == other._astuple()

    def __repr__(self):
        return f"{type(self).__name__}({', '.join(f'{f}={getattr(self, f)!r}' for f in self._fields)})"

    __hash__ = None


class Frozen(Record):
    """A record whose fields cannot be reassigned; hashable when its values are."""
    __slots__ = ()

    def __setattr__(self, name, value):
        raise AttributeError(f'cannot assign to field {name!r} of frozen {type(self).__name__}')

    def __delattr__(self, name):
        raise AttributeError(f'cannot delete field {name!r} of frozen {type(self).__name__}')

    def __hash__(self):
        return hash(self._astuple())

    def __reduce__(self):
        """copy, deepcopy and pickle rebuild through the constructor, as for a frozen
        dataclass; the default slot restore would hit __setattr__."""
        return (type(self), self._astuple())


try:
    import _json
except ImportError:
    _json = None

_CONSTANTS = {'-Infinity': float('-inf'), 'Infinity': float('inf'), 'NaN': float('nan')}


def _unique_pairs(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError('duplicate JSON key')
    return result


def _no_constant(value):
    raise ValueError('non-JSON numeric constant')


class _ScanCtx:
    __slots__ = ('object_pairs_hook', 'parse_constant', 'memo')
    strict = True
    object_hook = None
    parse_float = float
    parse_int = int
    parse_object = None
    parse_array = None
    parse_string = getattr(_json, 'scanstring', None)

    def __init__(self, pairs_hook, parse_constant):
        self.object_pairs_hook = pairs_hook
        self.parse_constant = parse_constant
        self.memo = {}


_ENC_STD = (_json.make_encoder(None, None, _json.encode_basestring_ascii, None, ': ', ', ', False, False, True)
            if _json is not None else None)
_ENC_COMPACT = (_json.make_encoder(None, None, _json.encode_basestring, None, ':', ',', False, False, False)
                if _json is not None else None)


def jdumps(value) -> str:
    if _ENC_STD is not None:
        return ''.join(_ENC_STD(value, 0))
    import json
    return json.dumps(value)


def jencode_compact(value) -> str:
    if _ENC_COMPACT is not None:
        return ''.join(_ENC_COMPACT(value, 0))
    import json
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def _scan(raw, pairs_hook, parse_constant):
    if isinstance(raw, (bytes, bytearray)):
        text = raw.decode('utf-8-sig')
    elif isinstance(raw, str):
        text = raw
    else:
        raise TypeError(f'the JSON object must be str, bytes or bytearray, not {type(raw).__name__}')
    if _json is not None:
        s = text.lstrip(' \t\n\r')
        if s:
            try:
                obj, end = _json.make_scanner(_ScanCtx(pairs_hook, parse_constant))(s, 0)
            except StopIteration:
                pass
            else:
                if end == len(s) or not s[end:].strip(' \t\n\r'):
                    return obj
    import json
    return json.loads(text, object_pairs_hook=pairs_hook, parse_constant=parse_constant)


def jloads(raw):
    return _scan(raw, None, _CONSTANTS.__getitem__)


def jloads_strict(text: str):
    if not isinstance(text, str):
        raise TypeError(f'the JSON object must be str, not {type(text).__name__}')
    return _scan(text, _unique_pairs, _no_constant)
