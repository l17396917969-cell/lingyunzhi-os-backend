from typing import Mapping, TypeVar
from onto_platform.proto_models import (
    OntologyRegistry,
    SharedPropertyTypeDefinition, InterfaceTypeDefinition,
    ObjectTypeDefinition, LinkTypeDefinition, ActionTypeDefinition,
    AssetMapping,
)
from onto_platform.registry.validator import validate, Finding
from onto_platform.registry.refs_scan import find_referrers, Referrer


class ValidationFailedError(Exception):
    def __init__(self, findings: list[Finding]):
        super().__init__(f"Validation failed with {len(findings)} finding(s)")
        self.findings = findings


class ReferencedError(Exception):
    def __init__(self, target_rid: str, referrers: list[Referrer]):
        super().__init__(f"{target_rid} is still referenced by {len(referrers)} location(s)")
        self.target_rid = target_rid
        self.referrers = referrers


T = TypeVar("T")


def _replace_map(src: Mapping[str, T], rid: str, defn: T | None) -> dict[str, T]:
    new = dict(src)
    if defn is None:
        new.pop(rid, None)
    else:
        new[rid] = defn
    return new


def _validate_or_raise(reg: OntologyRegistry, conn_ids: set[str]) -> None:
    findings = validate(reg, connection_ids=conn_ids)
    errs = [f for f in findings if f.is_error]
    if errs:
        raise ValidationFailedError(errs)


def _refuse_if_referenced(reg: OntologyRegistry, target_rid: str) -> None:
    refs = find_referrers(reg, target_rid)
    if refs:
        raise ReferencedError(target_rid, refs)


def put_shared_property_type(
    reg: OntologyRegistry, defn: SharedPropertyTypeDefinition, *, connection_ids: set[str],
) -> OntologyRegistry:
    candidate = reg.model_copy(update={
        "shared_property_types": _replace_map(reg.shared_property_types, defn.rid, defn),
    })
    _validate_or_raise(candidate, connection_ids)
    return candidate


def delete_shared_property_type(reg: OntologyRegistry, rid: str) -> OntologyRegistry:
    _refuse_if_referenced(reg, rid)
    return reg.model_copy(update={
        "shared_property_types": _replace_map(reg.shared_property_types, rid, None),
    })


def put_interface_type(
    reg: OntologyRegistry, defn: InterfaceTypeDefinition, *, connection_ids: set[str],
) -> OntologyRegistry:
    candidate = reg.model_copy(update={
        "interface_types": _replace_map(reg.interface_types, defn.rid, defn),
    })
    _validate_or_raise(candidate, connection_ids)
    return candidate


def delete_interface_type(reg: OntologyRegistry, rid: str) -> OntologyRegistry:
    _refuse_if_referenced(reg, rid)
    return reg.model_copy(update={
        "interface_types": _replace_map(reg.interface_types, rid, None),
    })


def put_object_type(
    reg: OntologyRegistry, defn: ObjectTypeDefinition, *, connection_ids: set[str],
) -> OntologyRegistry:
    candidate = reg.model_copy(update={
        "object_types": _replace_map(reg.object_types, defn.rid, defn),
    })
    _validate_or_raise(candidate, connection_ids)
    return candidate


def delete_object_type(reg: OntologyRegistry, rid: str) -> OntologyRegistry:
    _refuse_if_referenced(reg, rid)
    return reg.model_copy(update={
        "object_types": _replace_map(reg.object_types, rid, None),
    })


def put_link_type(
    reg: OntologyRegistry, defn: LinkTypeDefinition, *, connection_ids: set[str],
) -> OntologyRegistry:
    candidate = reg.model_copy(update={
        "link_types": _replace_map(reg.link_types, defn.rid, defn),
    })
    _validate_or_raise(candidate, connection_ids)
    return candidate


def delete_link_type(reg: OntologyRegistry, rid: str) -> OntologyRegistry:
    _refuse_if_referenced(reg, rid)
    return reg.model_copy(update={
        "link_types": _replace_map(reg.link_types, rid, None),
    })


def put_action_type(
    reg: OntologyRegistry, defn: ActionTypeDefinition, *, connection_ids: set[str],
) -> OntologyRegistry:
    candidate = reg.model_copy(update={
        "action_types": _replace_map(reg.action_types, defn.rid, defn),
    })
    _validate_or_raise(candidate, connection_ids)
    return candidate


def delete_action_type(reg: OntologyRegistry, rid: str) -> OntologyRegistry:
    _refuse_if_referenced(reg, rid)
    return reg.model_copy(update={
        "action_types": _replace_map(reg.action_types, rid, None),
    })


def set_asset_mapping(
    reg: OntologyRegistry, target_rid: str, mapping: AssetMapping,
    *, connection_ids: set[str],
) -> OntologyRegistry:
    if target_rid in reg.object_types:
        obj = reg.object_types[target_rid]
        new_obj = obj.model_copy(update={"asset_mapping": mapping})
        candidate = reg.model_copy(update={
            "object_types": _replace_map(reg.object_types, target_rid, new_obj),
        })
    elif target_rid in reg.link_types:
        lt = reg.link_types[target_rid]
        new_lt = lt.model_copy(update={"asset_mapping": mapping})
        candidate = reg.model_copy(update={
            "link_types": _replace_map(reg.link_types, target_rid, new_lt),
        })
    else:
        raise KeyError(f"Target RID {target_rid!r} not found in object_types or link_types")
    _validate_or_raise(candidate, connection_ids)
    return candidate
