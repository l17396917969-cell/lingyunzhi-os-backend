import re
from typing import Iterable
from onto_platform.proto_models import OntologyRegistry
from onto_platform.registry.validator import Finding, Severity, ValidatorCtx, checker


_RID_RE = re.compile(
    r"^ri\.(shprop|prop|iface|obj|link|action)\.[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_API_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")


_KIND_PREFIX = {
    "shared_property_types": "shprop",
    "interface_types": "iface",
    "object_types": "obj",
    "link_types": "link",
    "action_types": "action",
}


def _check_rid(rid: str, expected_prefix: str, path: str) -> Iterable[Finding]:
    m = _RID_RE.match(rid)
    if not m:
        yield Finding(
            severity=Severity.ERROR, code="RID_FORMAT", path=path,
            message=f"Invalid RID format (expected ri.{expected_prefix}.<uuid>): {rid!r}",
        )
        return
    if m.group(1) != expected_prefix:
        yield Finding(
            severity=Severity.ERROR, code="RID_FORMAT", path=path,
            message=f"RID prefix {m.group(1)!r} does not match entity kind {expected_prefix!r}",
        )


def _check_api_name(api_name: str, path: str) -> Iterable[Finding]:
    if not _API_NAME_RE.match(api_name):
        yield Finding(
            severity=Severity.ERROR, code="API_NAME_FORMAT", path=path,
            message=f"Invalid api_name {api_name!r} (must match {_API_NAME_RE.pattern})",
        )


@checker
def check_structural(registry: OntologyRegistry, ctx: ValidatorCtx) -> Iterable[Finding]:
    for kind_field, prefix in _KIND_PREFIX.items():
        entities = getattr(registry, kind_field)
        for rid, defn in entities.items():
            base_path = f"{kind_field}[{rid}]"
            yield from _check_rid(defn.rid, prefix, base_path + ".rid")
            if defn.api_name:
                yield from _check_api_name(defn.api_name, base_path + ".api_name")
            # nested PropertyTypes inside ObjectType / LinkType
            if hasattr(defn, "property_types"):
                for pt_key, pt in defn.property_types.items():
                    pt_path = f"{base_path}.property_types[{pt_key}]"
                    yield from _check_rid(pt.rid, "prop", pt_path + ".rid")
                    if pt.api_name:
                        yield from _check_api_name(pt.api_name, pt_path + ".api_name")
