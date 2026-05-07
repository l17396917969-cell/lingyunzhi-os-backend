import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import IngestionPage from "@/views/ingestion/IngestionPage";

describe("IngestionPage", () => {
  it("uploads a file then submits a job", async () => {
    const fetchMock = vi.spyOn(global, "fetch").mockImplementation(async (url: unknown, init?: RequestInit) => {
      if (String(url).includes("/api/whoami")) {
        return new Response(JSON.stringify({ token_label: "ed", scope: "editor", server_version: "0.1.0" }), { status: 200 });
      }
      if (String(url).includes("/uploads")) {
        return new Response(JSON.stringify({ upload_id: "u1", kind: "sql", size_bytes: 10 }), { status: 200 });
      }
      if (String(url).includes("/admin/ingestion/jobs") && init?.method === "POST") {
        return new Response(JSON.stringify({ job_id: "j1", status: "queued" }), { status: 200 });
      }
      return new Response(JSON.stringify({ items: [] }), { status: 200 });
    });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter><IngestionPage /></MemoryRouter>
      </QueryClientProvider>,
    );
    const file = new File(["CREATE TABLE T (id INT);"], "x.sql", { type: "text/plain" });
    await userEvent.upload(await screen.findByLabelText(/file/i), file);
    await userEvent.click(screen.getByRole("button", { name: /submit/i }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/admin/ingestion/jobs",
      expect.objectContaining({ method: "POST" }),
    ));
  });
});
