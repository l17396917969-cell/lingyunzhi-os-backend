import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getJob, cancelJob } from "@/api/ingestion";
import { DecisionsReport } from "@/components/DecisionsReport";

const TERMINAL = ["imported", "failed", "cancelled"];

export default function JobDetail() {
  const { job_id = "" } = useParams();
  const q = useQuery({
    queryKey: ["job", job_id],
    queryFn: () => getJob(job_id),
    refetchInterval: (query) => {
      const status = query.state.data?.status as string | undefined;
      return status && TERMINAL.includes(status) ? false : 2000;
    },
  });
  const job = q.data;
  return (
    <div className="space-y-4 p-8">
      <h1 className="text-xl font-semibold">Job {job_id}</h1>
      {q.isLoading || !job ? <div className="text-zinc-500 text-sm">Loading…</div> : (
        <>
          <div className="rounded border border-zinc-800 bg-zinc-900 p-3 text-xs">
            <div>Status: <strong>{String(job.status)}</strong> ({String(job.progress_pct)}%)</div>
            <div>Mode: {String(job.mode)}</div>
            {job.phase != null && <div>Phase: {String(job.phase)}</div>}
            {job.error_code != null && <div className="text-red-400">Error: {String(job.error_code)}</div>}
          </div>
          <section className="rounded border border-zinc-800 bg-zinc-900 p-3">
            <h3 className="mb-2 text-sm font-medium text-zinc-400">Decisions report</h3>
            <DecisionsReport data={(job.decisions_report ?? null) as Parameters<typeof DecisionsReport>[0]["data"]} />
          </section>
          {!TERMINAL.includes(String(job.status)) && (
            <button onClick={async () => { await cancelJob(job_id); void q.refetch(); }}
                    className="rounded bg-red-700 px-3 py-1 text-xs">Cancel</button>
          )}
        </>
      )}
    </div>
  );
}
