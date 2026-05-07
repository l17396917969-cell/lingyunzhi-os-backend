export type Env = "staging" | "production";

export function EnvSwitcher({ value, onChange }: { value: Env; onChange: (v: Env) => void }) {
  return (
    <div className="inline-flex rounded border border-zinc-700 bg-zinc-900 text-xs">
      {(["staging", "production"] as Env[]).map((e) => (
        <button
          key={e}
          onClick={() => onChange(e)}
          className={`px-3 py-1 capitalize ${e === value ? "bg-zinc-700" : ""}`}
        >
          {e}
        </button>
      ))}
    </div>
  );
}
