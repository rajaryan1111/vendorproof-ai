import { expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Evidence } from "./Processing";

it("renders page references and untrusted candidate text literally", () => {
  const source = {
    page: 1,
    segment: 0,
    start: 0,
    end: 8,
    original: "<script>",
    method: "native",
  };
  const { container } = render(
    <Evidence
      report={{
        document_id: "version",
        version_digest: "digest",
        schema_version: "fields/1",
        implementation: "local/1",
        classification: {
          category: "insurance",
          status: "suggested",
          evidence: [source],
        },
        pages: [{ number: 1, warning: "sparse_text", segments: [], words: 1 }],
        candidates: [
          {
            key: "policyholder",
            value: "<script>",
            normalized: "<script>",
            status: "candidate",
            source,
          },
        ],
      }}
    />,
  );
  expect(screen.getByText(/Page 1, segment 1/)).toBeTruthy();
  expect(screen.getByText(/sparse text/)).toBeTruthy();
  expect(container.querySelector("script")).toBeNull();
});
