import { Link, useLocation } from "react-router-dom";

export type Env = "staging" | "production";

export function EnvTabs({ basePath }: { basePath: "/graph" | "/browse" }) {
  const loc = useLocation();
  const env: Env = loc.pathname.endsWith("/production") ? "production" : "staging";
  return (
    <div className="inline-flex overflow-hidden rounded-md border border-zinc-700 text-sm">
      <Link
        to={`${basePath}/staging`}
        className={[
          "px-3 py-1.5",
          env === "staging"
            ? "bg-zinc-800 text-zinc-50"
            : "bg-zinc-950 text-zinc-400 hover:bg-zinc-900",
        ].join(" ")}
      >
        暂存区
      </Link>
      <Link
        to={`${basePath}/production`}
        className={[
          "px-3 py-1.5",
          env === "production"
            ? "bg-zinc-800 text-zinc-50"
            : "bg-zinc-950 text-zinc-400 hover:bg-zinc-900",
        ].join(" ")}
      >
        生产环境
      </Link>
    </div>
  );
}
