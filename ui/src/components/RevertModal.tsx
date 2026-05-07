import { useMutation, useQueryClient } from "@tanstack/react-query";
import { revertStagingToProduction } from "@/api/promote";
import { translateError } from "@/api/errorMessages";
import { ApiError } from "@/api/client";

export function RevertModal({ onClose, onReverted }: { onClose: () => void; onReverted: () => void }) {
  const qc = useQueryClient();
  const mut = useMutation({
    mutationFn: revertStagingToProduction,
    onSuccess: () => {
      qc.invalidateQueries();
      onReverted();
    },
  });
  const errorCode = mut.error instanceof ApiError ? mut.error.code : undefined;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="w-[420px] rounded-lg border border-zinc-700 bg-zinc-900 p-6" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-semibold">回退暂存</h2>
        <p className="mt-2 text-sm text-zinc-400">将暂存区重置为当前生产环境的内容。已在暂存区做出的所有变更将丢失。</p>
        {mut.isError && (
          <div className="mt-2 text-sm text-red-400">{translateError(errorCode)}</div>
        )}
        <div className="mt-5 flex justify-end gap-2">
          <button className="rounded px-3 py-1.5 text-sm text-zinc-400 hover:text-zinc-100" onClick={onClose}>
            取消
          </button>
          <button
            disabled={mut.isPending}
            onClick={() => mut.mutate()}
            className="rounded bg-amber-600 px-3 py-1.5 text-sm font-semibold disabled:opacity-40"
          >
            {mut.isPending ? "回退中…" : "确认回退"}
          </button>
        </div>
      </div>
    </div>
  );
}
