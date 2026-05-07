from enum import Enum
from onto_platform.proto_models import OntologyRegistry
from onto_platform.registry.crud import _validate_or_raise


class ImportMode(Enum):
    replace = "replace"
    merge = "merge"


def import_into_registry(
    base: OntologyRegistry,
    incoming: OntologyRegistry,
    *,
    mode: ImportMode,
    connection_ids: set[str],
) -> OntologyRegistry:
    if mode is ImportMode.replace:
        candidate = incoming.model_copy()
    elif mode is ImportMode.merge:
        candidate = base.model_copy(update={
            "version": incoming.version or base.version,
            "shared_property_types": {**base.shared_property_types, **incoming.shared_property_types},
            "interface_types": {**base.interface_types, **incoming.interface_types},
            "object_types": {**base.object_types, **incoming.object_types},
            "link_types": {**base.link_types, **incoming.link_types},
            "action_types": {**base.action_types, **incoming.action_types},
        })
    else:
        raise ValueError(f"Unknown ImportMode {mode!r}")
    _validate_or_raise(candidate, connection_ids)
    return candidate
