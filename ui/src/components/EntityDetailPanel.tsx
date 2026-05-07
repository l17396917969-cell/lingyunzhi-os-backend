export function EntityDetailPanel({ definition }: { definition: Record<string, unknown> | null }) {
  if (!definition) {
    return <div className="p-8 text-zinc-500">Pick an entity from the sidebar.</div>;
  }
  return (
    <pre className="overflow-auto rounded bg-zinc-950 p-4 text-xs">
      {JSON.stringify(definition, null, 2)}
    </pre>
  );
}
