import { Link, Outlet, useLocation } from "react-router-dom";
import { useSession } from "@/auth/session";

export function AppLayout() {
  const q = useSession();
  return (
    <div className="grid min-h-screen grid-cols-[16rem_1fr]">
      <aside className="flex flex-col border-r hairline bg-[var(--surface-1)]">
        {/* Brand mark */}
        <div className="px-5 pt-6 pb-5 border-b hairline">
          <Link to="/graph/staging" className="block">
            <div className="font-display text-[22px] font-medium leading-none tracking-tight text-zinc-100">
              本体平台
            </div>
            <div className="mt-1.5 flex items-center gap-2">
              <span className="pip pip-idle" />
              <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-zinc-400">
                Onto Platform
              </span>
            </div>
          </Link>
        </div>

        {/* Section label */}
        <div className="px-5 pt-5 pb-2">
          <div className="section-label">
            <span className="section-num">01</span> · 工作区
          </div>
        </div>

        <nav className="flex-1 px-3">
          <NavItem to="/graph/staging" index="A">图谱</NavItem>
          <NavItem to="/browse/staging" index="B">浏览器</NavItem>
          <NavItem to="/chat" index="C">注入</NavItem>
        </nav>

        {/* Footer: identity + scope + sign out */}
        <div className="border-t hairline px-5 py-4">
          <div className="section-label mb-2">
            <span className="section-num">02</span> · 当前会话
          </div>
          <div className="flex items-center gap-2">
            <span className="pip pip-ok" />
            <span className="font-mono text-[11px] text-zinc-300 truncate">
              {q.data?.token_label ?? "—"}
            </span>
          </div>
          <div className="mt-1 ml-4 text-[11px] text-zinc-400">
            权限 <span className="chip-mono ml-1.5 text-zinc-300">{translateScope(q.data?.scope)}</span>
          </div>
          <button
            type="button"
            className="mt-3 ml-4 font-mono text-[10px] uppercase tracking-[0.14em] text-zinc-400 hover:text-zinc-200"
            onClick={async () => {
              await fetch("/admin/logout", { method: "POST", credentials: "include" });
              window.location.href = "/login";
            }}
          >
            ↗ 退出登录
          </button>
        </div>
      </aside>

      <main className="overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}

function NavItem({
  to,
  children,
  index,
}: {
  to: string;
  children: React.ReactNode;
  index: string;
}) {
  const loc = useLocation();
  const prefix = "/" + to.split("/")[1];
  const isActive =
    loc.pathname === prefix || loc.pathname.startsWith(prefix + "/");
  return (
    <Link
      to={to}
      className={[
        "group relative flex items-center gap-3 rounded px-3 py-2.5 text-sm transition",
        isActive
          ? "nav-active-bar bg-[rgba(34,211,238,0.04)] text-zinc-50"
          : "text-zinc-400 hover:bg-zinc-900/40 hover:text-zinc-100",
      ].join(" ")}
    >
      <span
        className={[
          "font-mono text-[10px] tracking-[0.14em]",
          isActive ? "text-[var(--accent)]" : "text-zinc-600 group-hover:text-zinc-400",
        ].join(" ")}
      >
        {index}
      </span>
      <span className="flex-1 font-display text-[15px] font-normal tracking-wide">{children}</span>
    </Link>
  );
}

function translateScope(scope: string | undefined): string {
  if (scope === "admin") return "管理员";
  if (scope === "editor") return "编辑";
  if (scope === "read") return "只读";
  return "—";
}
