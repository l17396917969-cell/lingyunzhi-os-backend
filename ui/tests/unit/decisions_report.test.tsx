import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { DecisionsReport } from "@/components/DecisionsReport";

describe("DecisionsReport", () => {
  it("groups by tool and shows reasons", () => {
    render(<DecisionsReport data={{
      decisions: [
        { tool: "working_put_object_type", outcome: "ok", reason: "MD_MATERIAL", args_summary: {} },
        { tool: "working_put_object_type", outcome: "ok", reason: "MD_STATION", args_summary: {} },
        { tool: "working_put_link_type", outcome: "ok", reason: "stocked_at", args_summary: {} },
      ],
      imported_entity_counts: { object_types: 2, link_types: 1 },
    }} />);
    expect(screen.getByText(/working_put_object_type \(2\)/)).toBeInTheDocument();
    expect(screen.getByText(/MD_MATERIAL/)).toBeInTheDocument();
    expect(screen.getByText(/object_types=2/)).toBeInTheDocument();
  });
});
