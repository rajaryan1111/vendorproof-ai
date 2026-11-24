import { cleanup, render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { Login, signInAvailable } from "./workspace";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it.each([
  [503, { error: { code: "workspace_offline" } }],
  [200, { status: "validation_only" }],
])(
  "withholds the credential form when readiness is unavailable",
  async (status, body) => {
    const fetch = vi.fn(async () =>
      Response.json(body, { status: Number(status) }),
    );
    vi.stubGlobal("fetch", fetch);
    const router = createMemoryRouter(
      [{ path: "/login", Component: Login, loader: signInAvailable }],
      { initialEntries: ["/login"] },
    );
    render(<RouterProvider router={router} />);
    await screen.findByRole("heading", { name: "Workspace offline" });
    expect(screen.queryByLabelText("Password")).toBeNull();
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/health/db"),
      expect.objectContaining({ credentials: "omit", cache: "no-store" }),
    );
  },
);
