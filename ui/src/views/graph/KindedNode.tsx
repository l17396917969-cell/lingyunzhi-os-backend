import { Handle, Position, type NodeProps } from "reactflow";

interface KindStyle {
  color: string;
  bg: string;
  badgeClass: string;
  abbr: string;
}

const STYLE: Record<string, KindStyle> = {
  ObjectType: {
    color: "#22d3ee",
    bg: "rgba(34, 211, 238, 0.07)",
    badgeClass: "text-cyan-300",
    abbr: "OBJ",
  },
  LinkType: {
    color: "#34d399",
    bg: "rgba(52, 211, 153, 0.07)",
    badgeClass: "text-emerald-300",
    abbr: "LNK",
  },
  InterfaceType: {
    color: "#a78bfa",
    bg: "rgba(167, 139, 250, 0.07)",
    badgeClass: "text-violet-300",
    abbr: "IF",
  },
  SharedPropertyType: {
    color: "#fbbf24",
    bg: "rgba(251, 191, 36, 0.07)",
    badgeClass: "text-amber-300",
    abbr: "PROP",
  },
  ActionType: {
    color: "#fb7185",
    bg: "rgba(251, 113, 133, 0.07)",
    badgeClass: "text-rose-300",
    abbr: "ACT",
  },
};

const FALLBACK: KindStyle = {
  color: "#71717a",
  bg: "rgba(113, 113, 122, 0.07)",
  badgeClass: "text-zinc-400",
  abbr: "?",
};

export interface KindedNodeData {
  label: string;
  kind: string;
}

export function KindedNode({ data }: NodeProps<KindedNodeData>) {
  const s = STYLE[data.kind] ?? FALLBACK;
  return (
    <div
      className="relative flex items-center gap-2 rounded-sm border border-[var(--hairline-strong)] px-2.5 py-1.5"
      style={{
        borderLeft: `3px solid ${s.color}`,
        background: s.bg,
        minWidth: 170,
        backdropFilter: "blur(2px)",
      }}
    >
      <Handle
        type="target"
        position={Position.Left}
        style={{
          background: s.color,
          width: 6,
          height: 6,
          border: "none",
          opacity: 0.8,
        }}
      />
      <span
        className={`font-mono text-[9px] font-medium tracking-[0.14em] ${s.badgeClass}`}
        style={{ minWidth: 26 }}
      >
        {s.abbr}
      </span>
      <span className="truncate text-[12px] leading-none text-zinc-100">
        {data.label}
      </span>
      <Handle
        type="source"
        position={Position.Right}
        style={{
          background: s.color,
          width: 6,
          height: 6,
          border: "none",
          opacity: 0.8,
        }}
      />
    </div>
  );
}

export const KIND_LEGEND: { kind: string; label: string; color: string; abbr: string }[] = [
  { kind: "ObjectType", label: "对象类型", color: STYLE.ObjectType.color, abbr: STYLE.ObjectType.abbr },
  { kind: "LinkType", label: "关系类型", color: STYLE.LinkType.color, abbr: STYLE.LinkType.abbr },
  { kind: "InterfaceType", label: "接口类型", color: STYLE.InterfaceType.color, abbr: STYLE.InterfaceType.abbr },
  { kind: "SharedPropertyType", label: "共享属性", color: STYLE.SharedPropertyType.color, abbr: STYLE.SharedPropertyType.abbr },
  { kind: "ActionType", label: "动作类型", color: STYLE.ActionType.color, abbr: STYLE.ActionType.abbr },
];
