import { useQuery } from "@tanstack/react-query";
import { fetchSummary, fetchAuditRecent } from "@/api/ontology";

function EnvCard({ env }: { env: "staging" | "production" }) {
  const q = useQuery({ queryKey: ["summary", env], queryFn: () => fetchSummary(env) });
  if (q.isLoading || !q.data) return <div className="text-zinc-500">Loading {env}…</div>;
  const c = q.data.entity_counts;
  return (
    <section className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
      <h3 className="text-sm font-medium uppercase tracking-wide text-zinc-400">{env}</h3>
      <p className="mt-1 text-xs text-zinc-500">version {q.data.version}</p>
      <dl className="mt-3 grid grid-cols-5 gap-3 text-center">
        {(["shared_property_types","interface_types","object_types","link_types","action_types"] as const).map((k) => (
          <div key={k} className="rounded bg-zinc-950 p-2">
            <dt className="text-[10px] uppercase text-zinc-500">{k.replace(/_/g, " ").replace(" types", "")}</dt>
            <dd className="mt-1 text-lg font-semibold">{c[k]}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

export default function Dashboard() {
  const audit = useQuery({ queryKey: ["audit"], queryFn: fetchAuditRecent });
  return (
    <div className="space-y-6 p-8">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <EnvCard env="staging" />
        <EnvCard env="production" />
      </div>
      <section className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
        <h3 className="text-sm font-medium text-zinc-400">Recent activity</h3>
        <ul className="mt-3 divide-y divide-zinc-800 text-sm">
          {(audit.data?.items ?? []).map((it) => (
            <li key={it.id} className="flex justify-between py-2">
              <span><code>{it.tool}</code> by {it.token_label} ({it.scope})</span>
              <span className={it.outcome === "ok" ? "text-emerald-400" : "text-red-400"}>{it.outcome}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
