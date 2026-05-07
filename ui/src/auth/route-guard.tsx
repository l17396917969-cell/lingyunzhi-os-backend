import React from "react";
import { Navigate } from "react-router-dom";
import { useSession } from "./session";

export function RequireSession({ children }: { children: React.ReactNode }) {
  const q = useSession();
  if (q.isLoading) return <div className="p-8 text-zinc-400">Loading…</div>;
  if (!q.data) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
