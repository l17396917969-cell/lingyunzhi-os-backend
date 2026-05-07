import { describe, expect, it } from "vitest";
import { buildGraph } from "@/views/graph/build_graph";

describe("buildGraph", () => {
  it("creates IMPLEMENTS edge from ObjectType -> InterfaceType", () => {
    const reg = {
      version: "x",
      shared_property_types: {},
      interface_types: { "ri.iface.t": { rid: "ri.iface.t", api_name: "trackable", category: "OBJECT_INTERFACE" } },
      object_types: { "ri.obj.m": {
        rid: "ri.obj.m", api_name: "material",
        implements_interface_type_rids: ["ri.iface.t"],
      }},
      link_types: {}, action_types: {},
    };
    const g = buildGraph(reg as Parameters<typeof buildGraph>[0]);
    expect(g.nodes.find(n => n.id === "ri.obj.m")).toBeDefined();
    expect(g.edges.some(e =>
      e.source === "ri.obj.m" && e.target === "ri.iface.t" && e.data?.kind === "IMPLEMENTS"
    )).toBe(true);
  });

  it("creates CONNECTS edges for LinkType source/target", () => {
    const reg = {
      version: "x",
      shared_property_types: {}, interface_types: {},
      object_types: {
        "ri.obj.m": { rid: "ri.obj.m", api_name: "material" },
        "ri.obj.w": { rid: "ri.obj.w", api_name: "warehouse" },
      },
      link_types: { "ri.link.s": {
        rid: "ri.link.s", api_name: "stocked_at",
        source_object_type_rid: "ri.obj.m",
        target_object_type_rid: "ri.obj.w",
      }},
      action_types: {},
    };
    const g = buildGraph(reg as Parameters<typeof buildGraph>[0]);
    expect(g.edges.some(e =>
      e.source === "ri.obj.m" && e.target === "ri.link.s" && e.data?.kind === "CONNECTS"
    )).toBe(true);
    expect(g.edges.some(e =>
      e.source === "ri.link.s" && e.target === "ri.obj.w" && e.data?.kind === "CONNECTS"
    )).toBe(true);
  });
});
