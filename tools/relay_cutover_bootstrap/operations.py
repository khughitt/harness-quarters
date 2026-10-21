"""The fixed host operations: one table assembled from the concern modules.

To add host-side operations, define them in that concern's module as an `OPERATIONS` dict of
`hosts.Operation`s, import the module here and list its table in `OPERATIONS` below. Nothing
else registers operations; `hosts` reads this table when it validates or runs a request."""
from . import familiar, hosts, inputs, inventory, quiesce, restoration, surfaces, targets


def _assemble(*tables):
    assembled = {}
    for table in tables:
        for name, operation in table.items():
            if name in assembled or name in hosts.CONTROL:
                raise ValueError(f"operation {name} is defined twice")
            assembled[name] = operation
    return assembled


OPERATIONS = _assemble(inventory.OPERATIONS, inputs.OPERATIONS, quiesce.OPERATIONS,
                       targets.OPERATIONS, familiar.OPERATIONS, restoration.OPERATIONS,
                       surfaces.OPERATIONS)
