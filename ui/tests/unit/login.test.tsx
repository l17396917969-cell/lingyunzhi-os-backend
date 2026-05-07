import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Login } from "@/auth/login";

describe("Login", () => {
  it("submits the typed token", async () => {
    const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ label: "ed", scope: "editor" }), { status: 200 }),
    );
    render(<Login onSuccess={() => {}} />);
    await userEvent.type(screen.getByLabelText(/token/i), "op_xxx");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/admin/login", expect.objectContaining({
        method: "POST",
        credentials: "include",
      }));
    });
  });

  it("shows an error on 401", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: { code: "UNAUTHORIZED" } }), { status: 401 }),
    );
    render(<Login onSuccess={() => {}} />);
    await userEvent.type(screen.getByLabelText(/token/i), "op_bad");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByText(/invalid or revoked/i)).toBeInTheDocument();
  });
});
