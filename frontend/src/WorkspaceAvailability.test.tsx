import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { api, CheckingWorkspace, Login, loadAvailability } from "./workspace";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function open(path = "/login") {
  const router = createMemoryRouter(
    [
      {
        path: "/",
        loader: () => api("/account"),
        Component: () => null,
        HydrateFallback: CheckingWorkspace,
      },
      {
        path: "/login",
        Component: Login,
        loader: loadAvailability,
        HydrateFallback: CheckingWorkspace,
      },
    ],
    { initialEntries: [path] },
  );
  render(<RouterProvider router={router} />);
}

it("opens the hosted status page from a protected route and rechecks the real probe", async () => {
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json({ error: { code: "workspace_offline" } }, { status: 503 }),
    )
    .mockResolvedValueOnce(
      Response.json({ status: "validation_only", parser_probe_passed: false }),
    )
    .mockResolvedValueOnce(
      Response.json({ status: "validation_only", parser_probe_passed: true }),
    );
  vi.stubGlobal("fetch", fetch);
  open("/");
  await screen.findByRole("heading", { name: "Hosted workspace" });
  expect(screen.getByText("Connected")).toBeTruthy();
  expect(screen.getByText("Unavailable", { exact: true })).toBeTruthy();
  expect(screen.getByText(/Private PDF uploads/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Check again" }));
  await screen.findByText("Verified");
  expect(screen.queryByLabelText("Password")).toBeNull();
  expect(screen.queryByRole("button", { name: "Sign in" })).toBeNull();
  expect(document.querySelector('input[type="file"]')).toBeNull();
  expect(
    fetch.mock.calls.map(([url]) => new URL(url, "http://localhost").pathname),
  ).toEqual(["/api/v1/account", "/api/v1/health", "/api/v1/health"]);
  expect(fetch).toHaveBeenLastCalledWith(
    expect.stringContaining("/health"),
    expect.objectContaining({ credentials: "omit", cache: "no-store" }),
  );
});

it.each([
  [503, { error: { code: "workspace_offline" } }],
  [200, { status: "validation_only" }],
  [200, { status: "validation_only", parser_probe_passed: "yes" }],
])(
  "shows an offline state for an unverified health response",
  async (status, body) => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(Response.json(body, { status: Number(status) })),
    );
    open();
    await screen.findByRole("heading", { name: "Workspace offline" });
    expect(screen.queryByText("Connected")).toBeNull();
    expect(screen.queryByLabelText("Password")).toBeNull();
  },
);

it.each([false, true])(
  "gates the local login form on database readiness (%s)",
  async (ready) => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(Response.json({ status: "ok" }))
      .mockResolvedValueOnce(
        ready
          ? Response.json({ status: "ok" })
          : Response.json({}, { status: 503 }),
      );
    vi.stubGlobal("fetch", fetch);
    open();
    await screen.findByRole("heading", {
      name: ready ? "Sign in" : "Workspace offline",
    });
    expect(Boolean(screen.queryByLabelText("Password"))).toBe(ready);
    expect(fetch).toHaveBeenLastCalledWith(
      expect.stringContaining("/health/db"),
      expect.objectContaining({ credentials: "omit", cache: "no-store" }),
    );
  },
);
