from typing import Iterable
from onto_platform.proto_models import OntologyRegistry
from onto_platform.registry.validator import Finding, Severity, ValidatorCtx, checker


def _missing(
    rid: str,
    sp_set: set[str],
    iface_set: set[str],
    obj_set: set[str],
    link_set: set[str],
    action_set: set[str],
    kinds: tuple[str, ...],
) -> bool:
    """Return True if `rid` is non-empty and does not resolve in any of the named sets."""
    if not rid:
        return False
    pools: dict[str, set[str]] = {
        "shared_property_types": sp_set,
        "interface_types": iface_set,
        "object_types": obj_set,
        "link_types": link_set,
        "action_types": action_set,
    }
    for k in kinds:
        if rid in pools[k]:
            return False
    return True


@checker
def check_refs(registry: OntologyRegistry, ctx: ValidatorCtx) -> Iterable[Finding]:
    sp = set(registry.shared_property_types)
    ifaces = set(registry.interface_types)
    objs = set(registry.object_types)
    links = set(registry.link_types)
    actions = set(registry.action_types)

    def err(path: str, rid: str, expected: str) -> Finding:
        return Finding(
            severity=Severity.ERROR, code="REF_NOT_FOUND", path=path,
            message=f"Referenced {expected} {rid!r} does not exist",
            details={"rid": rid, "expected": expected},
        )

    # ObjectType refs
    for rid, obj in registry.object_types.items():
        base = f"object_types[{rid}]"
        for iface_rid in obj.implements_interface_type_rids:
            if _missing(iface_rid, sp, ifaces, objs, links, actions, ("interface_types",)):
                yield err(f"{base}.implements_interface_type_rids", iface_rid, "InterfaceType")
        for pt_rid in obj.primary_key_property_type_rids:
            # primary keys must be local PropertyType keys (not RIDs in main registry)
            local_rids = {pt.rid for pt in obj.property_types.values()}
            if pt_rid and pt_rid not in local_rids:
                yield err(f"{base}.primary_key_property_type_rids", pt_rid, "local PropertyType")
        for pt_key, pt in obj.property_types.items():
            ipath = f"{base}.property_types[{pt_key}].inherit_from_shared_property_type_rid"
            if _missing(pt.inherit_from_shared_property_type_rid, sp, ifaces, objs, links, actions, ("shared_property_types",)):
                yield err(ipath, pt.inherit_from_shared_property_type_rid, "SharedPropertyType")

    # LinkType refs
    for rid, lt in registry.link_types.items():
        base = f"link_types[{rid}]"
        if _missing(lt.source_object_type_rid, sp, ifaces, objs, links, actions, ("object_types",)):
            yield err(f"{base}.source_object_type_rid", lt.source_object_type_rid, "ObjectType")
        if _missing(lt.source_interface_type_rid, sp, ifaces, objs, links, actions, ("interface_types",)):
            yield err(f"{base}.source_interface_type_rid", lt.source_interface_type_rid, "InterfaceType")
        if _missing(lt.target_object_type_rid, sp, ifaces, objs, links, actions, ("object_types",)):
            yield err(f"{base}.target_object_type_rid", lt.target_object_type_rid, "ObjectType")
        if _missing(lt.target_interface_type_rid, sp, ifaces, objs, links, actions, ("interface_types",)):
            yield err(f"{base}.target_interface_type_rid", lt.target_interface_type_rid, "InterfaceType")
        for iface_rid in lt.implements_interface_type_rids:
            if _missing(iface_rid, sp, ifaces, objs, links, actions, ("interface_types",)):
                yield err(f"{base}.implements_interface_type_rids", iface_rid, "InterfaceType")
        local_rids = {pt.rid for pt in lt.property_types.values()}
        for pt_rid in lt.primary_key_property_type_rids:
            if pt_rid and pt_rid not in local_rids:
                yield err(f"{base}.primary_key_property_type_rids", pt_rid, "local PropertyType")
        for pt_key, pt in lt.property_types.items():
            ipath = f"{base}.property_types[{pt_key}].inherit_from_shared_property_type_rid"
            if _missing(pt.inherit_from_shared_property_type_rid, sp, ifaces, objs, links, actions, ("shared_property_types",)):
                yield err(ipath, pt.inherit_from_shared_property_type_rid, "SharedPropertyType")

    # InterfaceType refs
    for rid, iface in registry.interface_types.items():
        base = f"interface_types[{rid}]"
        for parent in iface.extends_interface_type_rids:
            if _missing(parent, sp, ifaces, objs, links, actions, ("interface_types",)):
                yield err(f"{base}.extends_interface_type_rids", parent, "InterfaceType")
        for sp_rid in iface.required_shared_property_type_rids:
            if _missing(sp_rid, sp, ifaces, objs, links, actions, ("shared_property_types",)):
                yield err(f"{base}.required_shared_property_type_rids", sp_rid, "SharedPropertyType")

    # ActionType refs
    for rid, action in registry.action_types.items():
        base = f"action_types[{rid}]"
        for i, p in enumerate(action.parameters):
            if _missing(p.derived_from_object_type_rid, sp, ifaces, objs, links, actions, ("object_types",)):
                yield err(f"{base}.parameters[{i}].derived_from_object_type_rid", p.derived_from_object_type_rid, "ObjectType")
            if _missing(p.derived_from_link_type_rid, sp, ifaces, objs, links, actions, ("link_types",)):
                yield err(f"{base}.parameters[{i}].derived_from_link_type_rid", p.derived_from_link_type_rid, "LinkType")
            if _missing(p.derived_from_interface_type_rid, sp, ifaces, objs, links, actions, ("interface_types",)):
                yield err(f"{base}.parameters[{i}].derived_from_interface_type_rid", p.derived_from_interface_type_rid, "InterfaceType")
