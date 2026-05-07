import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import Dashboard from "@/views/dashboard/Dashboard";

describe("Dashboard", () => {
  it("renders entity counts for both envs", async () => {
    vi.spyOn(global, "fetch").mockImplementation(async (url: unknown) => {
      if (String(url).includes("/api/whoami")) {
        return new Response(JSON.stringify({ token_label: "ed", scope: "editor", server_version: "0.1.0" }), { status: 200 });
      }
      if (String(url).endsWith("/staging/summary")) {
        return new Response(JSON.stringify({ env: "staging", version: 3,
          entity_counts: { shared_property_types: 1, interface_types: 1,
                           object_types: 4, link_types: 2, action_types: 0 }}), { status: 200 });
      }
      if (String(url).endsWith("/production/summary")) {
        return new Response(JSON.stringify({ env: "production", version: 2,
          entity_counts: { shared_property_types: 1, interface_types: 0,
                           object_types: 3, link_types: 1, action_types: 0 }}), { status: 200 });
      }
      return new Response(JSON.stringify({ items: [] }), { status: 200 });
    });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter><Dashboard /></MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByText(/staging/i)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("4")).toBeInTheDocument());  // staging object_types
    await waitFor(() => expect(screen.getByText("3")).toBeInTheDocument());  // production object_types
  });
});
