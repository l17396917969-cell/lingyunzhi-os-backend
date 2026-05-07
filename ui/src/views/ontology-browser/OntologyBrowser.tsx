import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchFull } from "@/api/ontology";
import { useSession } from "@/auth/session";
import { EntityDetailPanel } from "@/components/EntityDetailPanel";
import { EnvTabs } from "@/components/EnvTabs";
import { PromoteModal } from "@/components/PromoteModal";
import { RevertModal } from "@/components/RevertModal";

const KINDS = [
  ["object_types", "对象类型"],
  ["link_types", "关系类型"],
  ["interface_types", "接口类型"],
  ["shared_property_types", "共享属性"],
  ["action_types", "动作类型"],
] as const;

type AnyEntity = { rid: string; api_name?: string; display_name?: string };

export default function OntologyBrowser() {
  const { env = "staging" } = useParams();
  const session = useSession();
  const isAdmin = session.data?.scope === "admin";
  const [promote, setPromote] = useState(false);
  const [revert, setRevert] = useState(false);
  const q = useQuery({ queryKey: ["full", env], queryFn: () => fetchFull(env as "staging" | "production") });
  const [filter, setFilter] = useState("");
  const [selected, setSelected] = useState<{ kind: string; rid: string } | null>(null);
  const reg = q.data;
  const matches = (e: AnyEntity) =>
    !filter ||
    (e?.api_name?.toLowerCase().includes(filter.toLowerCase()) ?? false) ||
    (e?.display_name?.toLowerCase().includes(filter.toLowerCase()) ?? false);
  const selectedDef = useMemo(() => {
    if (!reg || !selected) return null;
    return (reg as unknown as Record<string, Record<string, unknown>>)[selected.kind][selected.rid] as Record<string, unknown>;
  }, [reg, selected]);

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b hairline px-6 py-3.5">
        <div className="flex items-baseline gap-4">
          <span className="section-label">
            <span className="section-num">B</span> · 浏览器
          </span>
          <h1 className="font-display text-[22px] font-medium tracking-tight text-zinc-100">浏览器</h1>
          <EnvTabs basePath="/browse" />
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
      <div className="grid flex-1 grid-cols-[20rem_1fr] overflow-hidden">
        <aside className="overflow-auto border-r hairline p-3">
          <input
            aria-label="filter"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="筛选…"
            className="mb-3 w-full rounded-sm border border-[var(--hairline-strong)] bg-[var(--surface-0)] p-2 text-xs focus:border-[var(--accent)] focus:outline-none"
          />
          {q.isLoading && <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-zinc-600">加载中…</div>}
          {KINDS.map(([k, label]) => {
            const items = Object.values(
              (reg as unknown as Record<string, Record<string, AnyEntity>>)?.[k] ?? {},
            ).filter(matches);
            return (
              <details key={k} open className="mt-3">
                <summary className="flex cursor-pointer items-center justify-between py-1.5 section-label">
                  <span>{label}</span>
                  <span className="text-zinc-700">{items.length}</span>
                </summary>
                <ul className="mt-1 space-y-0.5">
                  {items.map((e: AnyEntity) => (
                    <li key={e.rid}>
                      <button
                        onClick={() => setSelected({ kind: k, rid: e.rid })}
                        className={`block w-full rounded-sm px-2 py-1 text-left font-mono text-[11.5px] ${
                          selected?.rid === e.rid
                            ? "bg-[rgba(34,211,238,0.08)] text-zinc-100"
                            : "text-zinc-400 hover:bg-zinc-900/60 hover:text-zinc-200"
                        }`}
                      >
                        {e.api_name || e.rid}
                      </button>
                    </li>
                  ))}
                </ul>
              </details>
            );
          })}
        </aside>
        <section className="overflow-auto p-6">
          <EntityDetailPanel definition={selectedDef} />
        </section>
      </div>
      {promote && (
        <PromoteModal
          onClose={() => setPromote(false)}
          onPromoted={() => {
            setPromote(false);
            window.location.href = "/browse/production";
          }}
        />
      )}
      {revert && (
        <RevertModal onClose={() => setRevert(false)} onReverted={() => setRevert(false)} />
      )}
    </div>
  );
}
