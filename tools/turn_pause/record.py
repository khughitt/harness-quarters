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
