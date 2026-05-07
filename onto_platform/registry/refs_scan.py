from dataclasses import dataclass
from onto_platform.proto_models import OntologyRegistry


@dataclass
class Referrer:
    rid: str         # the referring entity's RID
    kind: str        # "object_type" | "link_type" | "interface_type" | "property_type" | "action_type"
    field: str       # short field name, e.g. "implements_interface_type_rids"
    path: str        # full dotted path including the field


def _add(out: list[Referrer], rid: str, kind: str, field: str, path: str) -> None:
    out.append(Referrer(rid=rid, kind=kind, field=field, path=path))


def find_referrers(registry: OntologyRegistry, target_rid: str) -> list[Referrer]:
    out: list[Referrer] = []

    # ObjectType
    for rid, obj in registry.object_types.items():
        if target_rid in obj.implements_interface_type_rids:
            _add(out, rid, "object_type", "implements_interface_type_rids",
                 f"object_types[{rid}].implements_interface_type_rids")
        for k, pt in obj.property_types.items():
            if pt.inherit_from_shared_property_type_rid == target_rid:
                _add(out, rid, "property_type", "inherit_from_shared_property_type_rid",
                     f"object_types[{rid}].property_types[{k}].inherit_from_shared_property_type_rid")
            if pt.rid == target_rid:
                _add(out, rid, "property_type", "rid",
                     f"object_types[{rid}].property_types[{k}].rid")

    # LinkType
    for rid, lt in registry.link_types.items():
        for fld in (
            "source_object_type_rid", "source_interface_type_rid",
            "target_object_type_rid", "target_interface_type_rid",
        ):
            if getattr(lt, fld) == target_rid:
                _add(out, rid, "link_type", fld, f"link_types[{rid}].{fld}")
        if target_rid in lt.implements_interface_type_rids:
            _add(out, rid, "link_type", "implements_interface_type_rids",
                 f"link_types[{rid}].implements_interface_type_rids")
        for k, pt in lt.property_types.items():
            if pt.inherit_from_shared_property_type_rid == target_rid:
                _add(out, rid, "property_type", "inherit_from_shared_property_type_rid",
                     f"link_types[{rid}].property_types[{k}].inherit_from_shared_property_type_rid")

    # InterfaceType
    for rid, iface in registry.interface_types.items():
        if target_rid in iface.extends_interface_type_rids:
            _add(out, rid, "interface_type", "extends_interface_type_rids",
                 f"interface_types[{rid}].extends_interface_type_rids")
        if target_rid in iface.required_shared_property_type_rids:
            _add(out, rid, "interface_type", "required_shared_property_type_rids",
                 f"interface_types[{rid}].required_shared_property_type_rids")

    # ActionType
    for rid, action in registry.action_types.items():
        for i, p in enumerate(action.parameters):
            for fld in (
                "derived_from_object_type_rid",
                "derived_from_link_type_rid",
                "derived_from_interface_type_rid",
            ):
                if getattr(p, fld) == target_rid:
                    _add(out, rid, "action_type", fld,
                         f"action_types[{rid}].parameters[{i}].{fld}")

    return out
