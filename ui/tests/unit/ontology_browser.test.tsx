import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import OntologyBrowser from "@/views/ontology-browser/OntologyBrowser";

describe("OntologyBrowser", () => {
  it("clicking a sidebar entity shows its definition", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(new Response(JSON.stringify({
      version: "x", shared_property_types: {}, interface_types: {}, link_types: {}, action_types: {},
      object_types: { "ri.obj.aaa": { rid: "ri.obj.aaa", api_name: "material" } },
    }), { status: 200 }));
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/browse/staging"]}>
          <Routes>
            <Route path="/browse/:env" element={<OntologyBrowser />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const item = await screen.findByText("material");
    await userEvent.click(item);
    expect(await screen.findByText(/"rid": "ri.obj.aaa"/)).toBeInTheDocument();
  });
});
