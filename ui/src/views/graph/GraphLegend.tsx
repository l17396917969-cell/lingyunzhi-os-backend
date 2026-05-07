import { KIND_LEGEND } from "./KindedNode";

export function GraphLegend() {
  return (
    <div className="absolute right-3 top-3 z-10 rounded-sm border border-[var(--hairline-strong)] bg-[var(--surface-1)]/85 px-3 py-2 backdrop-blur">
      <div className="mb-1.5 font-mono text-[9px] uppercase tracking-[0.18em] text-zinc-400">
        图例 · LEGEND
      </div>
      <ul className="flex flex-col gap-1">
        {KIND_LEGEND.map((it) => (
          <li key={it.kind} className="flex items-center gap-2 text-[11px]">
            <span
              className="inline-block"
              style={{
                width: 14,
                height: 10,
                borderLeft: `3px solid ${it.color}`,
                background: "var(--surface-2)",
              }}
            />
            <span
              className="font-mono text-[10px] tracking-[0.04em] text-zinc-400"
              style={{ minWidth: 32 }}
            >
              {it.abbr}
            </span>
            <span className="text-zinc-300">{it.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
