import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { computeDiffCounts, promoteStagingToProduction, type DiffCounts } from "@/api/promote";
import { translateError } from "@/api/errorMessages";
import { ApiError } from "@/api/client";

interface DiffSummaryProps {
  counts: DiffCounts;
}

function DiffSummary({ counts }: DiffSummaryProps) {
  const rows: { label: string; key: keyof DiffCounts["added"] }[] = [
    { label: "对象类型", key: "object_types" },
    { label: "关系类型", key: "link_types" },
    { label: "共享属性", key: "shared_property_types" },
    { label: "接口类型", key: "interface_types" },
    { label: "动作类型", key: "action_types" },
  ];
  return (
    <table className="w-full">
      <thead>
        <tr className="text-zinc-500">
          <th className="text-left">类型</th>
          <th className="text-right">+</th>
          <th className="text-right">−</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.key}>
            <td>{r.label}</td>
            <td className="text-right text-emerald-400">+{counts.added[r.key]}</td>
            <td className="text-right text-red-400">−{counts.removed[r.key]}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function PromoteModal({ onClose, onPromoted }: { onClose: () => void; onPromoted: () => void }) {
  const qc = useQueryClient();
  const [confirmText, setConfirmText] = useState("");
  const counts = useQuery({ queryKey: ["promote-diff"], queryFn: computeDiffCounts });
  const mut = useMutation({
    mutationFn: promoteStagingToProduction,
    onSuccess: () => {
      qc.invalidateQueries();
      onPromoted();
    },
  });
  const errorCode = mut.error instanceof ApiError ? mut.error.code : undefined;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="w-[480px] rounded-lg border border-zinc-700 bg-zinc-900 p-6" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-semibold">推送到生产</h2>
        <p className="mt-2 text-sm text-zinc-400">将暂存区的全部变更推送到生产环境。此操作不可直接撤销。</p>
        <div className="mt-4 rounded border border-zinc-800 bg-zinc-950 p-3 text-xs">
          {counts.isLoading ? (
            <div>计算差异中…</div>
          ) : counts.data ? (
            <DiffSummary counts={counts.data} />
          ) : (
            <div className="text-red-400">无法计算差异</div>
          )}
        </div>
        <label className="mt-4 block text-sm">
          请输入 PROMOTE 以确认
          <input
            aria-label="confirm-promote"
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
            className="mt-1 w-full rounded border border-zinc-700 bg-zinc-950 p-2 font-mono"
          />
        </label>
        {mut.isError && (
          <div className="mt-2 text-sm text-red-400">{translateError(errorCode)}</div>
        )}
        <div className="mt-5 flex justify-end gap-2">
          <button className="rounded px-3 py-1.5 text-sm text-zinc-400 hover:text-zinc-100" onClick={onClose}>
            取消
          </button>
          <button
            disabled={confirmText !== "PROMOTE" || mut.isPending}
            onClick={() => mut.mutate()}
            className="rounded bg-emerald-600 px-3 py-1.5 text-sm font-semibold disabled:opacity-40"
          >
            {mut.isPending ? "推送中…" : "确认推送"}
          </button>
        </div>
      </div>
    </div>
  );
}
