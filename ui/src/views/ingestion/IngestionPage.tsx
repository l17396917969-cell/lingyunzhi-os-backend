import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { listJobs, submitJob, uploadFile, type JobRow } from "@/api/ingestion";

export default function IngestionPage() {
  const qc = useQueryClient();
  const jobs = useQuery({ queryKey: ["jobs"], queryFn: listJobs, refetchInterval: 5000 });
  const [files, setFiles] = useState<File[]>([]);
  const [mode, setMode] = useState<"replace" | "merge">("merge");
  const [instructions, setInstructions] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submitMut = useMutation({
    mutationFn: async () => {
      const ups = await Promise.all(files.map(uploadFile));
      return submitJob(ups.map((u) => u.upload_id), mode, instructions || undefined);
    },
    onSuccess: () => { setFiles([]); setInstructions(""); qc.invalidateQueries({ queryKey: ["jobs"] }); },
    onError: (e: unknown) => setError(String((e as { message?: string })?.message ?? e)),
  });

  return (
    <div className="space-y-6 p-8">
      <h1 className="text-2xl font-semibold">Ingestion</h1>
      <section className="rounded border border-zinc-800 bg-zinc-900 p-4">
        <h3 className="text-sm font-medium text-zinc-400">New job</h3>
        <label className="mt-3 block text-xs">
          File(s)
          <input
            aria-label="file"
            type="file" multiple
            onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
            accept=".sql,.pdf,.docx,.pptx,.xlsx"
            className="mt-1 block"
          />
        </label>
        <label className="mt-3 block text-xs">
          Mode
          <select value={mode} onChange={(e) => setMode(e.target.value as "replace" | "merge")}
                  className="ml-2 rounded border border-zinc-700 bg-zinc-950 p-1">
            <option value="merge">merge</option>
            <option value="replace">replace</option>
          </select>
        </label>
        <label className="mt-3 block text-xs">
          Instructions (optional)
          <textarea value={instructions} onChange={(e) => setInstructions(e.target.value)}
                    className="mt-1 w-full rounded border border-zinc-700 bg-zinc-950 p-2" rows={3} />
        </label>
        {error && <div role="alert" className="mt-2 text-xs text-red-400">{error}</div>}
        <button
          disabled={files.length === 0 || submitMut.isPending}
          onClick={() => submitMut.mutate()}
          className="mt-3 rounded bg-emerald-600 px-3 py-1 text-sm disabled:opacity-50">
          Submit
        </button>
      </section>
      <section className="rounded border border-zinc-800 bg-zinc-900 p-4">
        <h3 className="text-sm font-medium text-zinc-400">Recent jobs</h3>
        <ul className="mt-3 divide-y divide-zinc-800 text-xs">
          {(jobs.data?.items ?? []).map((j: JobRow) => (
            <li key={j.id} className="flex justify-between py-2">
              <Link to={`/ingest/${j.id}`} className="text-emerald-400 underline">
                {j.id}
              </Link>
              <span className="text-zinc-500">{j.mode}</span>
              <span>{j.status}</span>
              <span>{j.progress_pct}%</span>
              {j.error_code && <span className="text-red-400">{j.error_code}</span>}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
