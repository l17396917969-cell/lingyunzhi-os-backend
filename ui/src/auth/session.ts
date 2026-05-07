import { useQuery } from "@tanstack/react-query";
import { api, ApiError } from "@/api/client";

export interface Whoami { token_label: string; scope: "read" | "editor" | "admin"; server_version: string }

export function useSession() {
  return useQuery<Whoami | null>({
    queryKey: ["whoami"],
    queryFn: async () => {
      try {
        return await api<Whoami>("/api/whoami");
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null;
        throw e;
      }
    },
    retry: false,
    staleTime: 30_000,
  });
}
