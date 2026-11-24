import { afterEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { createMemoryRouter, Outlet, RouterProvider } from "react-router-dom";
import { ExceptionDetail, Queue } from "./Exceptions";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
const member = { id: "reviewer", email: "reviewer@example.invalid" };
const item = {
  id: "f",
  supplier_id: "s",
  supplier: "Synthetic supplier",
  run_id: "run",
  rule: "requirement",
  outcome: "missing_document",
  severity: "medium",
  created_at: "2026-01-01T00:00:00Z",
  status: "open",
  assignee: null,
  owner: null,
  revision: 0,
  archived: false,
};
const guide = {
  why: "The agreement is missing.",
  action: "Please provide the agreement.",
  subjects: ["Documentation request", "Agreement request"],
  sentences: ["Please provide the agreement.", "Thank you."],
  subject: "Documentation request",
  message: "Please provide the agreement.",
};
const detail = {
  ...item,
  guidance: guide,
  can_edit: true,
  transitions: ["resolved"],
  evidence: [],
  history: [],
  drafts: [],
  corrections: [],
  replacement_targets: [],
  comparison: null,
  page: 1,
};
function mount(role = "admin", d = detail) {
  const router = createMemoryRouter([
    {
      path: "/",
      element: <Outlet context={{ role }} />,
      children: [
        {
          index: true,
          Component: ExceptionDetail,
          loader: () => ({ d, members: [member] }),
        },
      ],
    },
  ]);
  return render(<RouterProvider router={router} />);
}
it("submits filters and sort and shows the filtered workload", async () => {
  const loader = vi.fn(({ request }: { request: Request }) => ({
    data: {
      counts: { total: 1, mine: 0, unassigned: 1 },
      items: [item],
      page: 1,
    },
    members: [member],
    url: request.url,
  }));
  const router = createMemoryRouter([{ path: "/", Component: Queue, loader }]);
  render(<RouterProvider router={router} />);
  await screen.findByText("Synthetic supplier · requirement");
  fireEvent.change(screen.getByLabelText("Ownership"), {
    target: { value: "unassigned" },
  });
  fireEvent.change(screen.getByLabelText("Sort by"), {
    target: { value: "age" },
  });
  fireEvent.click(screen.getByText("Apply filters"));
  await waitFor(() =>
    expect(router.state.location.search).toContain("owner=unassigned"),
  );
  expect(router.state.location.search).toContain("sort=age");
  expect(screen.getByText(/1 matching/)).toBeTruthy();
});
it("assigns ownership and records confirmed decisions with the observed revision", async () => {
  const send = vi.fn(async () => Response.json({ seq: 1 }));
  vi.stubGlobal("fetch", send);
  mount();
  await screen.findByLabelText("Assign to");
  fireEvent.change(screen.getByLabelText("Assign to"), {
    target: { value: "reviewer" },
  });
  fireEvent.change(screen.getByLabelText("Assignment reason"), {
    target: { value: "Inspect agreement." },
  });
  fireEvent.click(screen.getByText("Record assignment"));
  await screen.findByText("Assignment recorded");
  expect(send).toHaveBeenCalledWith(
    expect.stringContaining("/assignment"),
    expect.objectContaining({
      body: JSON.stringify({
        previous: 0,
        assignee: "reviewer",
        reason: "Inspect agreement.",
      }),
    }),
  );
  fireEvent.change(screen.getByLabelText("Decision reason"), {
    target: { value: "Reviewed agreement." },
  });
  fireEvent.click(screen.getByLabelText(/I reviewed/));
  fireEvent.click(screen.getByText("Record decision"));
  await screen.findByText("Decision recorded");
});
it("previews edited supplier text and saves a revision", async () => {
  const send = vi.fn(async () => Response.json({ revision: 1 }));
  vi.stubGlobal("fetch", send);
  mount("reviewer");
  await screen.findByLabelText("Draft subject");
  fireEvent.change(screen.getByLabelText("Draft subject"), {
    target: { value: "Agreement request" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Thank you." }));
  expect(
    screen.getByText("Please provide the agreement. Thank you.", {
      selector: "p",
    }),
  ).toBeTruthy();
  fireEvent.click(screen.getByText("Save draft"));
  await screen.findByText("Draft saved");
  expect(send).toHaveBeenCalledTimes(1);
});
it("withholds mutation controls for an auditor", async () => {
  mount("auditor", { ...detail, can_edit: false, transitions: [] });
  await screen.findByText("Corrective guidance");
  for (const name of [
    "Save draft",
    "Record assignment",
    "Upload correction",
    "Record decision",
  ])
    expect(screen.queryByRole("button", { name })).toBeNull();
});
it("uploads the linked PDF and reports a rejected operation", async () => {
  const send = vi.fn(async () => new Response(null, { status: 409 }));
  vi.stubGlobal("fetch", send);
  mount("operator", { ...detail, can_edit: false, transitions: [] });
  await screen.findByLabelText("Corrected PDF");
  const file = new File(["synthetic"], "synthetic.pdf", {
    type: "application/pdf",
  });
  fireEvent.change(screen.getByLabelText("Corrected PDF"), {
    target: { files: [file] },
  });
  fireEvent.click(screen.getByLabelText("Confirm corrected version"));
  fireEvent.submit(screen.getByLabelText("Corrected PDF").closest("form")!);
  await screen.findByRole("alert");
  expect(send).toHaveBeenCalledWith(
    expect.stringMatching(/documents\?finding_id=f&request_id=/),
    expect.objectContaining({ method: "POST" }),
  );
});
