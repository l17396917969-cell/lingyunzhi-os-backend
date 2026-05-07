import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchDiff, promote, revert, undoPromote } from "@/api/lifecycle";
import { useSession } from "@/auth/session";

const KINDS = ["object_types", "link_types", "interface_types", "shared_property_types", "action_types"] as const;

function ConfirmModal({
  word, onConfirm, onCancel,
}: { word: "PROMOTE" | "REVERT"; onConfirm: (extra?: string) => void; onCancel: () => void }) {
  const [typed, setTyped] = useState("");
  const [msg, setMsg] = useState("");
  const ok = typed === word;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="w-96 space-y-3 rounded border border-zinc-700 bg-zinc-900 p-4">
        <h3 className="text-sm font-semibold">{word === "PROMOTE" ? "Promote staging to production" : "Revert staging"}</h3>
        <label className="block text-xs">
          Type &ldquo;{word}&rdquo; to confirm
          <input
            aria-label={`type "${word}"`}
            value={typed} onChange={(e) => setTyped(e.target.value)}
            className="mt-1 w-full rounded border border-zinc-700 bg-zinc-950 p-2"
          />
        </label>
        {word === "PROMOTE" && (
          <label className="block text-xs">Commit message
            <input value={msg} onChange={(e) => setMsg(e.target.value)}
                   className="mt-1 w-full rounded border border-zinc-700 bg-zinc-950 p-2" />
          </label>
        )}
        <div className="flex justify-end gap-2 text-xs">
          <button onClick={onCancel} className="rounded bg-zinc-700 px-3 py-1">Cancel</button>
          <button disabled={!ok} onClick={() => onConfirm(msg)}
                  className="rounded bg-emerald-600 px-3 py-1 disabled:opacity-50">
            Confirm {word.toLowerCase()}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function DiffView() {
  const session = useSession();
  const qc = useQueryClient();
  const diff = useQuery({ queryKey: ["diff"], queryFn: fetchDiff });
  const [confirm, setConfirm] = useState<"PROMOTE" | "REVERT" | null>(null);
  const [flash, setFlash] = useState<string | null>(null);

  const promoteMut = useMutation({ mutationFn: (msg: string) => promote(msg),
    onSuccess: () => { setFlash("Production updated."); qc.invalidateQueries({ queryKey: ["summary"] }); qc.invalidateQueries({ queryKey: ["diff"] }); }});
  const revertMut = useMutation({ mutationFn: () => revert(),
    onSuccess: () => { setFlash("Staging reverted to production."); qc.invalidateQueries({ queryKey: ["diff"] }); }});
  const undoMut = useMutation({ mutationFn: () => undoPromote(),
    onSuccess: () => { setFlash("Last promote undone."); qc.invalidateQueries({ queryKey: ["diff"] }); }});

  const isAdmin = session.data?.scope === "admin";

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Diff: staging vs production</h1>
        <div className="flex gap-2">
          <button disabled={!isAdmin} onClick={() => undoMut.mutate()}
                  className="rounded bg-zinc-700 px-3 py-1 text-sm disabled:opacity-50"
                  title={!isAdmin ? "Requires admin scope" : ""}>Undo last promote</button>
          <button disabled={!isAdmin} onClick={() => setConfirm("REVERT")}
                  className="rounded bg-red-700 px-3 py-1 text-sm disabled:opacity-50"
                  title={!isAdmin ? "Requires admin scope" : ""}>Revert staging</button>
          <button disabled={!isAdmin} onClick={() => setConfirm("PROMOTE")}
                  className="rounded bg-emerald-600 px-3 py-1 text-sm disabled:opacity-50"
                  title={!isAdmin ? "Requires admin scope" : ""}>Promote</button>
        </div>
      </div>
      {flash && <div role="status" className="rounded bg-zinc-900 p-2 text-xs">{flash}</div>}
      {(["added", "removed", "modified"] as const).map((bucket) => (
        <section key={bucket} className="rounded border border-zinc-800 bg-zinc-900 p-4">
          <h3 className="text-sm font-medium uppercase tracking-wide text-zinc-400">{bucket}</h3>
          <div className="mt-3 grid gap-2 text-xs">
            {KINDS.map((k) => {
              const items = (diff.data as unknown as Record<string, Record<string, unknown>>)?.[bucket]?.[k] ?? {};
              const rids = Object.keys(items as object);
              if (!rids.length) return null;
              return (
                <details key={k}>
                  <summary>{k} ({rids.length})</summary>
                  <ul className="mt-1 ml-4 list-disc">
                    {rids.map((r) => <li key={r}>{r}</li>)}
                  </ul>
                </details>
              );
            })}
          </div>
        </section>
      ))}
      {confirm && (
        <ConfirmModal
          word={confirm}
          onConfirm={(msg) => { confirm === "PROMOTE" ? promoteMut.mutate(msg ?? "") : revertMut.mutate(); setConfirm(null); }}
          onCancel={() => setConfirm(null)}
        />
      )}
    </div>
  );
}
