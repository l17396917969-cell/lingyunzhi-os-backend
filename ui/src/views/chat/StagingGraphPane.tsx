import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import ReactFlow, { Background, Controls, MiniMap, type Node } from "reactflow";
import dagre from "@dagrejs/dagre";
import "reactflow/dist/style.css";
import { fetchFull } from "@/api/ontology";
import { buildGraph } from "@/views/graph/build_graph";
import { KindedNode } from "@/views/graph/KindedNode";
import { GraphLegend } from "@/views/graph/GraphLegend";

function layout(nodes: Node[], edges: { source: string; target: string }[]) {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "LR", nodesep: 30, ranksep: 78 });
  g.setDefaultEdgeLabel(() => ({}));
  for (const n of nodes) g.setNode(n.id, { width: 200, height: 44 });
  for (const e of edges) g.setEdge(e.source, e.target);
  dagre.layout(g);
  return nodes.map((n) => {
    const p = g.node(n.id);
    return { ...n, position: { x: p.x - 100, y: p.y - 22 } };
  });
}

const NODE_TYPES = { kinded: KindedNode };

export function StagingGraphPane({ turnInFlight }: { turnInFlight: boolean }) {
  const q = useQuery({ queryKey: ["full", "staging"], queryFn: () => fetchFull("staging") });
  const { nodes, edges } = useMemo(() => {
    if (!q.data) return { nodes: [], edges: [] };
    const g = buildGraph(q.data as Parameters<typeof buildGraph>[0]);
    return { nodes: layout(g.nodes, g.edges), edges: g.edges };
  }, [q.data]);

  return (
    <div className="flex h-full flex-col bg-[var(--surface-0)]">
      {/* Header */}
      <div className="border-b hairline px-4 py-3">
        <div className="flex items-baseline justify-between">
          <div className="flex items-baseline gap-3">
            <span className="section-label">
              <span className="section-num">02</span> · 暂存图谱
            </span>
            <span className="font-display text-[16px] font-medium text-zinc-100">
              Staging
            </span>
          </div>
          <div className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.14em]">
            {turnInFlight ? (
              <>
                <span className="pip pip-warn pulse-soft" />
                <span className="text-amber-300/90">处理中</span>
              </>
            ) : (
              <>
                <span className="pip pip-ok" />
                <span className="text-emerald-300/80">已同步</span>
              </>
            )}
          </div>
        </div>
        <div className="mt-1.5 flex items-center gap-3 font-mono text-[10px] uppercase tracking-[0.14em] text-zinc-400">
          <span>nodes · {nodes.length}</span>
          <span className="text-zinc-700">·</span>
          <span>edges · {edges.length}</span>
        </div>
      </div>

      {/* Graph */}
      <div className="relative flex-1">
        {q.isLoading && (
          <div className="absolute inset-0 flex items-center justify-center font-mono text-[11px] uppercase tracking-[0.14em] text-zinc-400">
            加载图谱…
          </div>
        )}
        {!q.isLoading && nodes.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center text-center">
            <div>
              <div className="font-display text-[14px] text-zinc-500">暂存区为空</div>
              <div className="mt-1 font-mono text-[10px] uppercase tracking-[0.14em] text-zinc-700">
                empty staging registry
              </div>
            </div>
          </div>
        )}
        <ReactFlow nodes={nodes} edges={edges} nodeTypes={NODE_TYPES} fitView className="bg-transparent">
          <Background gap={32} color="rgba(244,244,245,0.04)" />
          <Controls className="!bg-zinc-900 !border-zinc-800" />
          <MiniMap
            pannable
            zoomable
            maskColor="rgba(9, 9, 11, 0.85)"
            nodeColor="rgba(34, 211, 238, 0.4)"
            className="!bg-zinc-900 !border-zinc-800"
          />
        </ReactFlow>
        {nodes.length > 0 && <GraphLegend />}
      </div>
    </div>
  );
}
