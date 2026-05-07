import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import ReactFlow, { Background, Controls, MiniMap, type Node } from "reactflow";
import dagre from "@dagrejs/dagre";
import "reactflow/dist/style.css";
import { fetchFull } from "@/api/ontology";
import { useSession } from "@/auth/session";
import { EnvTabs } from "@/components/EnvTabs";
import { PromoteModal } from "@/components/PromoteModal";
import { RevertModal } from "@/components/RevertModal";
import { buildGraph } from "./build_graph";
import { KindedNode } from "./KindedNode";
import { GraphLegend } from "./GraphLegend";

function layout(nodes: Node[], edges: { source: string; target: string }[]) {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "LR", nodesep: 32, ranksep: 88 });
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

export default function GraphView() {
  const { env = "staging" } = useParams();
  const session = useSession();
  const isAdmin = session.data?.scope === "admin";
  const [promote, setPromote] = useState(false);
  const [revert, setRevert] = useState(false);
  const q = useQuery({ queryKey: ["full", env], queryFn: () => fetchFull(env as "staging" | "production") });
  const { nodes, edges } = useMemo(() => {
    if (!q.data) return { nodes: [], edges: [] };
    const g = buildGraph(q.data as Parameters<typeof buildGraph>[0]);
    return { nodes: layout(g.nodes, g.edges), edges: g.edges };
  }, [q.data]);
  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b hairline px-6 py-3.5">
        <div className="flex items-baseline gap-4">
          <span className="section-label">
            <span className="section-num">A</span> · 图谱
          </span>
          <h1 className="font-display text-[22px] font-medium tracking-tight text-zinc-100">图谱</h1>
          <EnvTabs basePath="/graph" />
        </div>
        {env === "staging" && isAdmin && (
          <div className="flex gap-2">
            <button
              type="button"
              className="rounded-sm border border-emerald-700/40 bg-emerald-950/30 px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.14em] text-emerald-300 hover:border-emerald-500 hover:bg-emerald-900/40 hover:text-emerald-200"
              onClick={() => setPromote(true)}
            >
              推送到生产 →
            </button>
            <button
              type="button"
              className="rounded-sm border border-amber-700/40 bg-amber-950/20 px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.14em] text-amber-300 hover:border-amber-500 hover:bg-amber-900/30 hover:text-amber-200"
              onClick={() => setRevert(true)}
            >
              ↺ 回退暂存
            </button>
          </div>
        )}
      </header>
      <div className="relative flex-1">
        <ReactFlow nodes={nodes} edges={edges} nodeTypes={NODE_TYPES} fitView className="bg-transparent">
          <Background gap={32} color="rgba(244,244,245,0.04)" />
          <Controls className="!bg-zinc-900 !border-zinc-800" />
          <MiniMap maskColor="rgba(9, 9, 11, 0.85)" nodeColor="rgba(34, 211, 238, 0.4)" className="!bg-zinc-900 !border-zinc-800" />
        </ReactFlow>
        <GraphLegend />
      </div>
      {promote && (
        <PromoteModal
          onClose={() => setPromote(false)}
          onPromoted={() => {
            setPromote(false);
            window.location.href = "/graph/production";
          }}
        />
      )}
      {revert && (
        <RevertModal onClose={() => setRevert(false)} onReverted={() => setRevert(false)} />
      )}
    </div>
  );
}
