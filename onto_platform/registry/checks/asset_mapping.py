from typing import Iterable
from onto_platform.proto_models import OntologyRegistry, AssetMapping
from onto_platform.registry.validator import Finding, Severity, ValidatorCtx, checker


def _is_empty(am: AssetMapping) -> bool:
    return not (am.read_connection_id or am.read_asset_path or am.writeback_enabled)


def _check(am: AssetMapping, base: str, conn_ids: set[str]) -> Iterable[Finding]:
    if _is_empty(am):
        yield Finding(
            severity=Severity.WARNING, code="ASSET_MAPPING_EMPTY", path=base,
            message="No AssetMapping configured (cannot run query_sql against this entity)",
        )
        return
    if am.read_connection_id and am.read_connection_id not in conn_ids:
        yield Finding(
            severity=Severity.ERROR, code="ASSET_MAPPING_CONNECTION_NOT_FOUND",
            path=f"{base}.read_connection_id",
            message=f"Connection {am.read_connection_id!r} is not registered",
            details={"connection_id": am.read_connection_id},
        )


@checker
def check_asset_mapping(registry: OntologyRegistry, ctx: ValidatorCtx) -> Iterable[Finding]:
    for rid, obj in registry.object_types.items():
        yield from _check(obj.asset_mapping, f"object_types[{rid}].asset_mapping", ctx.connection_ids)
    for rid, lt in registry.link_types.items():
        yield from _check(lt.asset_mapping, f"link_types[{rid}].asset_mapping", ctx.connection_ids)
