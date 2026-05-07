type Decision = { tool: string; outcome: string; reason: string; args_summary: unknown; error?: string };

export function DecisionsReport({ data }: { data: { decisions: Decision[]; imported_entity_counts?: Record<string, number> } | null }) {
  if (!data) return <div className="text-zinc-500 text-xs">No decisions yet.</div>;
  const groups = new Map<string, Decision[]>();
  for (const d of data.decisions) {
    const arr = groups.get(d.tool) ?? [];
    arr.push(d);
    groups.set(d.tool, arr);
  }
  return (
    <div className="space-y-3 text-xs">
      {data.imported_entity_counts && (
        <div className="text-zinc-500">
          Imported: {Object.entries(data.imported_entity_counts)
            .map(([k, v]) => `${k}=${v}`).join("  ")}
        </div>
      )}
      {[...groups.entries()].map(([tool, items]) => (
        <details key={tool} open>
          <summary className="cursor-pointer">{tool} ({items.length})</summary>
          <ul className="ml-4 mt-1 list-disc space-y-1">
            {items.map((d, i) => (
              <li key={i}>
                <span className={d.outcome === "ok" ? "text-emerald-400" : "text-red-400"}>{d.outcome}</span>
                {" — "}{d.reason || JSON.stringify(d.args_summary)}
                {d.error && <span className="text-red-400"> ({d.error})</span>}
              </li>
            ))}
          </ul>
        </details>
      ))}
    </div>
  );
}
