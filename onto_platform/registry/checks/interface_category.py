from typing import Iterable
from onto_platform.proto_models import OntologyRegistry, InterfaceCategory
from onto_platform.registry.validator import Finding, Severity, ValidatorCtx, checker


@checker
def check_interface_category(registry: OntologyRegistry, ctx: ValidatorCtx) -> Iterable[Finding]:
    ifaces = registry.interface_types

    for rid, iface in ifaces.items():
        base = f"interface_types[{rid}]"

        # Rule 1: shape compatibility with category
        if iface.category is InterfaceCategory.OBJECT_INTERFACE:
            if iface.object_constraint is not None:
                yield Finding(
                    severity=Severity.ERROR, code="INTERFACE_CATEGORY_MISMATCH",
                    path=f"{base}.object_constraint",
                    message="OBJECT_INTERFACE must not carry object_constraint",
                )
        elif iface.category is InterfaceCategory.LINK_INTERFACE:
            if iface.link_requirements:
                yield Finding(
                    severity=Severity.ERROR, code="INTERFACE_CATEGORY_MISMATCH",
                    path=f"{base}.link_requirements",
                    message="LINK_INTERFACE must not carry link_requirements",
                )
        else:
            yield Finding(
                severity=Severity.ERROR, code="INTERFACE_CATEGORY_INVALID",
                path=f"{base}.category",
                message=f"Interface category {iface.category!r} is invalid",
            )

        # Rule 2: extended interfaces must share category
        for parent_rid in iface.extends_interface_type_rids:
            parent = ifaces.get(parent_rid)
            if parent is None:
                continue  # already flagged by refs checker
            if parent.category != iface.category:
                yield Finding(
                    severity=Severity.ERROR, code="INTERFACE_EXTENDS_CATEGORY_MISMATCH",
                    path=f"{base}.extends_interface_type_rids",
                    message=f"Cannot extend {parent_rid} ({parent.category}) from interface of category {iface.category}",
                )

    # Rule 3: detect cycles via DFS over EXTENDS
    color: dict[str, int] = {}  # 0=unseen, 1=in-progress, 2=done

    def visit(rid: str, stack: list[str]) -> Iterable[Finding]:
        if color.get(rid, 0) == 1:
            cycle = stack[stack.index(rid):] + [rid]
            yield Finding(
                severity=Severity.ERROR, code="INTERFACE_EXTENDS_CYCLE",
                path=f"interface_types[{rid}].extends_interface_type_rids",
                message=f"Cycle detected: {' -> '.join(cycle)}",
                details={"cycle": cycle},
            )
            return
        if color.get(rid, 0) == 2:
            return
        color[rid] = 1
        stack.append(rid)
        node = ifaces.get(rid)
        if node:
            for parent in node.extends_interface_type_rids:
                if parent in ifaces:
                    yield from visit(parent, stack)
        stack.pop()
        color[rid] = 2

    for rid in ifaces:
        if color.get(rid, 0) == 0:
            yield from visit(rid, [])
