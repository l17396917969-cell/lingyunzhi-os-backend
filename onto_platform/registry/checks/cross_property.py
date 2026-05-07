import re
from typing import Iterable
from onto_platform.proto_models import OntologyRegistry, ObjectTypeDefinition, LinkTypeDefinition
from onto_platform.registry.validator import Finding, Severity, ValidatorCtx, checker

_REF_RE = re.compile(r"\{([a-z][a-z0-9_]*)\}")


def _check_entity(entity: ObjectTypeDefinition | LinkTypeDefinition, base: str) -> Iterable[Finding]:
    api_names = {pt.api_name for pt in entity.property_types.values() if pt.api_name}
    for i, rule in enumerate(entity.validation.rules):
        if rule.cross_property is None:
            continue
        expr = rule.cross_property.expression
        for ref in _REF_RE.findall(expr):
            if ref not in api_names:
                yield Finding(
                    severity=Severity.ERROR, code="CROSS_PROPERTY_UNRESOLVED",
                    path=f"{base}.validation.rules[{i}].cross_property.expression",
                    message=f"Reference {{{ref}}} does not resolve to a property of this entity",
                    details={"reference": ref, "available": sorted(api_names)},
                )


@checker
def check_cross_property(registry: OntologyRegistry, ctx: ValidatorCtx) -> Iterable[Finding]:
    for rid, obj in registry.object_types.items():
        yield from _check_entity(obj, f"object_types[{rid}]")
    for rid, lt in registry.link_types.items():
        yield from _check_entity(lt, f"link_types[{rid}]")
