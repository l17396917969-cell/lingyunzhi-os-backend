from typing import Iterable
from onto_platform.proto_models import OntologyRegistry, PropertyTypeDefinition, SharedPropertyTypeDefinition
from onto_platform.registry.validator import Finding, Severity, ValidatorCtx, checker


def _check_one(
    pt: PropertyTypeDefinition,
    base: str,
    sps: dict[str, SharedPropertyTypeDefinition],
) -> Iterable[Finding]:
    has_physical = bool(pt.physical_column)
    has_virtual = bool(pt.virtual_expression)
    if not has_physical and not has_virtual:
        yield Finding(
            severity=Severity.ERROR, code="PROPERTY_BACKING_MISSING", path=base,
            message="PropertyType must set either physical_column or virtual_expression",
        )
    elif has_physical and has_virtual:
        yield Finding(
            severity=Severity.ERROR, code="PROPERTY_BACKING_BOTH_SET", path=base,
            message="PropertyType must set only one of physical_column or virtual_expression",
        )
    if pt.inherit_from_shared_property_type_rid:
        sp = sps.get(pt.inherit_from_shared_property_type_rid)
        if sp is not None and pt.data_type != sp.data_type:
            yield Finding(
                severity=Severity.ERROR, code="INHERITED_DATA_TYPE_MISMATCH",
                path=f"{base}.data_type",
                message=(
                    f"Inherited data_type mismatch: local={pt.data_type}, "
                    f"shared({pt.inherit_from_shared_property_type_rid})={sp.data_type}"
                ),
                details={"local": str(pt.data_type), "shared": str(sp.data_type)},
            )


@checker
def check_property_backing(registry: OntologyRegistry, ctx: ValidatorCtx) -> Iterable[Finding]:
    sps = registry.shared_property_types
    for rid, obj in registry.object_types.items():
        for k, pt in obj.property_types.items():
            yield from _check_one(pt, f"object_types[{rid}].property_types[{k}]", sps)
    for rid, lt in registry.link_types.items():
        for k, pt in lt.property_types.items():
            yield from _check_one(pt, f"link_types[{rid}].property_types[{k}]", sps)
