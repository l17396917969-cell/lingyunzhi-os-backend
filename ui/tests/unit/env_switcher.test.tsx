import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EnvSwitcher } from "@/components/EnvSwitcher";

describe("EnvSwitcher", () => {
  it("calls onChange when toggled", async () => {
    const onChange = vi.fn();
    render(<EnvSwitcher value="staging" onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: /production/i }));
    expect(onChange).toHaveBeenCalledWith("production");
  });
});
