import type { Edge, Node } from "reactflow";

export interface OntologyForGraph {
  shared_property_types: Record<string, AnyOntologyEntity>;
  interface_types: Record<string, AnyOntologyEntity>;
  object_types: Record<string, AnyOntologyEntity>;
  link_types: Record<string, AnyOntologyEntity>;
  action_types: Record<string, AnyOntologyEntity>;
}

interface AnyOntologyEntity {
  rid: string;
  api_name?: string;
  implements_interface_type_rids?: string[];
  extends_interface_type_rids?: string[];
  required_shared_property_type_rids?: string[];
  source_object_type_rid?: string;
  target_object_type_rid?: string;
  property_types?: Record<string, PropertyTypeEntry>;
  parameters?: ActionParameter[];
}

interface PropertyTypeEntry {
  rid: string;
  inherit_from_shared_property_type_rid?: string;
}

interface ActionParameter {
  derived_from_object_type_rid?: string;
  derived_from_link_type_rid?: string;
  derived_from_interface_type_rid?: string;
}

const KIND_OF: Record<string, string> = {
  shprop: "SharedPropertyType",
  iface: "InterfaceType",
  obj: "ObjectType",
  link: "LinkType",
  action: "ActionType",
};

function kindFromRid(rid: string): string {
  const m = rid.match(/^ri\.([^.]+)\./);
  return m ? KIND_OF[m[1]] ?? m[1] : "?";
}

function pushEdge(out: Edge[], source: string, target: string, kind: string) {
  out.push({ id: `${kind}:${source}->${target}`, source, target, data: { kind }, type: "default" });
}

export function buildGraph(reg: OntologyForGraph): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  const all = [
    ...Object.values(reg.shared_property_types),
    ...Object.values(reg.interface_types),
    ...Object.values(reg.object_types),
    ...Object.values(reg.link_types),
    ...Object.values(reg.action_types),
  ];
  for (const e of all) {
    nodes.push({
      id: e.rid,
      data: { label: e.api_name || e.rid, kind: kindFromRid(e.rid) },
      position: { x: 0, y: 0 },
      type: "kinded",
    });
  }
  for (const obj of Object.values(reg.object_types)) {
    for (const ifaceRid of obj.implements_interface_type_rids ?? []) {
      pushEdge(edges, obj.rid, ifaceRid, "IMPLEMENTS");
    }
  }
  for (const lt of Object.values(reg.link_types)) {
    if (lt.source_object_type_rid) pushEdge(edges, lt.source_object_type_rid, lt.rid, "CONNECTS");
    if (lt.target_object_type_rid) pushEdge(edges, lt.rid, lt.target_object_type_rid, "CONNECTS");
    for (const ifaceRid of lt.implements_interface_type_rids ?? []) {
      pushEdge(edges, lt.rid, ifaceRid, "IMPLEMENTS");
    }
  }
  for (const iface of Object.values(reg.interface_types)) {
    for (const parent of iface.extends_interface_type_rids ?? []) {
      pushEdge(edges, iface.rid, parent, "EXTENDS");
    }
    for (const sp of iface.required_shared_property_type_rids ?? []) {
      pushEdge(edges, iface.rid, sp, "REQUIRES");
    }
  }
  for (const obj of Object.values(reg.object_types)) {
    for (const pt of Object.values(obj.property_types ?? {})) {
      if (pt.inherit_from_shared_property_type_rid) {
        pushEdge(edges, pt.rid, pt.inherit_from_shared_property_type_rid, "BASED_ON");
      }
    }
  }
  for (const action of Object.values(reg.action_types)) {
    for (const p of action.parameters ?? []) {
      const t = p.derived_from_object_type_rid || p.derived_from_link_type_rid || p.derived_from_interface_type_rid;
      if (t) pushEdge(edges, action.rid, t, "OPERATES_ON");
    }
  }
  return { nodes, edges };
}
