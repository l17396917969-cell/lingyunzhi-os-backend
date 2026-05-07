import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import DiffView from "@/views/diff/DiffView";

describe("DiffView", () => {
  it("disables Promote when scope < admin", async () => {
    vi.spyOn(global, "fetch").mockImplementation(async (url: unknown) => {
      if (String(url).includes("/api/whoami")) {
        return new Response(JSON.stringify({ token_label: "ed", scope: "editor", server_version: "0.1.0" }), { status: 200 });
      }
      return new Response(JSON.stringify({ added: {}, removed: {}, modified: {} }), { status: 200 });
    });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter><DiffView /></MemoryRouter>
      </QueryClientProvider>,
    );
    // "Promote" button (exact), not "Undo last promote"
    const btn = await screen.findByRole("button", { name: /^promote$/i });
    expect(btn).toBeDisabled();
  });

  it("requires confirmation typing for revert", async () => {
    vi.spyOn(global, "fetch").mockImplementation(async (url: unknown) => {
      if (String(url).includes("/api/whoami")) {
        return new Response(JSON.stringify({ token_label: "boss", scope: "admin", server_version: "0.1.0" }), { status: 200 });
      }
      if (String(url).includes("/revert")) {
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }
      return new Response(JSON.stringify({ added: {}, removed: {}, modified: {} }), { status: 200 });
    });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter><DiffView /></MemoryRouter>
      </QueryClientProvider>,
    );
    await userEvent.click(await screen.findByRole("button", { name: /revert staging/i }));
    await userEvent.type(await screen.findByLabelText(/type "REVERT"/i), "REVERT");
    await userEvent.click(screen.getByRole("button", { name: /confirm revert/i }));
    expect(await screen.findByText(/staging reverted/i)).toBeInTheDocument();
  });
});
