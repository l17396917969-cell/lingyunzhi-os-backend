# onto_platform/registry/diff.py
from typing import Any

from onto_platform.proto_models import OntologyRegistry


_KINDS = (
    "shared_property_types",
    "interface_types",
    "object_types",
    "link_types",
    "action_types",
)


def compute_diff(
    staging: OntologyRegistry, production: OntologyRegistry
) -> dict[str, Any]:
    added: dict[str, dict[str, Any]] = {k: {} for k in _KINDS}
    removed: dict[str, dict[str, Any]] = {k: {} for k in _KINDS}
    modified: dict[str, dict[str, Any]] = {k: {} for k in _KINDS}
    for k in _KINDS:
        s = getattr(staging, k)
        p = getattr(production, k)
        for rid, defn in s.items():
            if rid not in p:
                added[k][rid] = defn.model_dump()
            elif defn != p[rid]:
                modified[k][rid] = {
                    "staging": defn.model_dump(),
                    "production": p[rid].model_dump(),
                }
        for rid, defn in p.items():
            if rid not in s:
                removed[k][rid] = defn.model_dump()
    return {"added": added, "removed": removed, "modified": modified}
