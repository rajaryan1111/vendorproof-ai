import { useEffect, useState, type FormEvent } from "react";
import { apiBase } from "./api";

const categories = ["registration", "tax", "bank", "insurance", "agreement"];
type Rule = {
  category: string;
  when_type: string | null;
  when_jurisdiction: string | null;
  expiry: boolean;
  issue_date: boolean;
  identifier_scheme: string | null;
};
type Policy = {
  jurisdiction: string | null;
  supplier_type: string | null;
  days: number;
  legal_suffix_aliases: boolean;
  rules: Rule[];
};
type Config = { version: number; body: Policy };
type Run = {
  id: string;
  created_at: string;
  policy_version: number;
  rule_version: string;
  as_of: string;
};
type Ref = {
  document: string;
  digest: string;
  attempt: string | null;
  field?: string;
  page?: number;
  start?: number;
  end?: number;
  segment?: number;
  method?: string;
  original?: string;
  normalized?: string;
  category?: string;
  heading_locations?: { page: number; start: number; end: number }[];
};
type Event = {
  seq: number;
  actor: string;
  status: string;
  reason?: string;
  created_at: string;
};
type Finding = {
  id: string;
  rule: string;
  outcome: string;
  explanation: string;
  severity: string;
  quality: string;
  requires_review: boolean;
  status: string;
  evidence: Ref[];
  history: Event[];
};
type Result = Run & {
  findings: Finding[];
  inventory: Ref[];
  checklist: {
    category: string;
    outcome: string;
    expiry_check: boolean;
    when_type: string | null;
    when_jurisdiction: string | null;
  }[];
};
const label = (s: string) => s.replaceAll("_", " ");
async function request<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch(apiBase + path, {
    method,
    credentials: "include",
    cache: "no-store",
    headers: {
      "X-VP-Request": "1",
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok)
    throw Error(
      response.status === 409
        ? "This record has changed. Refresh and try again."
        : response.status === 422
          ? "The request exceeds a limit or contains invalid fields."
          : "Verification request failed. Check access and connection.",
    );
  return response.json();
}
function PolicyEditor({
  config,
  save,
  busy,
}: {
  config: Config;
  save: (p: Policy) => void;
  busy: boolean;
}) {
  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const val = (k: string) => String(form.get(k) || "").trim() || null;
    save({
      jurisdiction: val("jurisdiction"),
      supplier_type: val("type"),
      days: Number(val("days")),
      legal_suffix_aliases: form.has("aliases"),
      rules: categories
        .filter((k) => form.has(k))
        .map((k) => ({
          category: k,
          when_type: val(k + "type"),
          when_jurisdiction: val(k + "location"),
          expiry: form.has(k + "expiry"),
          issue_date: form.has(k + "issue"),
          identifier_scheme: val(k + "scheme"),
        })),
    });
  }
  const p = config.body;
  return (
    <details>
      <summary>Configure requirements</summary>
      <form onSubmit={submit}>
        <label>
          Supplier type
          <input name="type" defaultValue={p.supplier_type ?? ""} />
        </label>
        <label>
          Supplier jurisdiction
          <input name="jurisdiction" defaultValue={p.jurisdiction ?? ""} />
        </label>
        <label>
          Expiry warning window (days)
          <input
            type="number"
            required
            min="0"
            max="365"
            name="days"
            defaultValue={p.days}
          />
        </label>
        <label>
          <input
            type="checkbox"
            name="aliases"
            defaultChecked={p.legal_suffix_aliases}
          />
          Recognize Pvt Ltd and Ltd suffix aliases
        </label>
        {categories.map((k) => {
          const r = p.rules.find((s) => s.category === k);
          return (
            <fieldset key={k}>
              <legend>{label(k)}</legend>
              <label>
                <input type="checkbox" name={k} defaultChecked={!!r} />
                Require {k}
              </label>
              <label>
                Only for supplier type
                <input name={k + "type"} defaultValue={r?.when_type ?? ""} />
              </label>
              <label>
                Only for jurisdiction
                <input
                  name={k + "location"}
                  defaultValue={r?.when_jurisdiction ?? ""}
                />
              </label>
              <label>
                <input
                  type="checkbox"
                  name={k + "expiry"}
                  defaultChecked={r?.expiry}
                />
                Check expiry
              </label>
              <label>
                <input
                  type="checkbox"
                  name={k + "issue"}
                  defaultChecked={r?.issue_date}
                />
                Check issue date
              </label>
              <label>
                Identifier namespace
                <select
                  name={k + "scheme"}
                  defaultValue={r?.identifier_scheme ?? ""}
                >
                  <option value="">Unconfigured</option>
                  <option value="exact_local">
                    Same local registry (exact format)
                  </option>
                  <option value="uk_company">UK company number</option>
                </select>
              </label>
            </fieldset>
          );
        })}
        <button disabled={busy}>Save policy version</button>
      </form>
    </details>
  );
}
function Evidence({ refs, sourcePath }: { refs: Ref[]; sourcePath?: string }) {
  const [source, setSource] = useState<string | null>(null);
  async function open(index: number) {
    try {
      const detail = await request<{
        excerpt: string;
        page: number;
        method: string;
        bbox: number[] | null;
      }>(sourcePath + "/" + index);
      setSource(
        "Page " +
          detail.page +
          " · " +
          detail.method +
          " · " +
          detail.excerpt +
          (detail.bbox
            ? " · bounds " + detail.bbox.map((n) => n.toFixed(1)).join(", ")
            : ""),
      );
    } catch {
      setSource("Source unavailable. Refresh the run to check access.");
    }
  }
  return (
    <details>
      <summary>Source evidence ({refs.length})</summary>
      {!refs.length && (
        <p>The policy was evaluated against an empty document inventory.</p>
      )}
      <div className="vp-comparison">
        {refs.map((r, i) => (
          <div key={i}>
            <strong>
              {label(r.field ?? r.category ?? "Document version")}
            </strong>
            {r.original !== undefined && (
              <p>
                {r.original}{" "}
                {r.normalized && <small>· Normalized: {r.normalized}</small>}
              </p>
            )}
            <p>
              Version {r.document}
              {r.page && " · Page " + r.page}
            </p>
            {r.segment !== undefined && (
              <p>
                Segment {r.segment + 1} · characters {r.start}–{r.end} ·{" "}
                {r.method}
              </p>
            )}
            {sourcePath && r.original !== undefined && (
              <button onClick={() => void open(i)}>Open cited span</button>
            )}
            {r.heading_locations?.map((h, j) => (
              <small key={j}>
                Heading · page {h.page}, characters {h.start}–{h.end}{" "}
              </small>
            ))}
            <small>
              Digest {r.digest} · Attempt {r.attempt ?? "none"}
            </small>
          </div>
        ))}
      </div>
      {source && <p role="status">{source}</p>}
    </details>
  );
}
export function Verification({
  sid,
  role,
  archived,
}: {
  sid: string;
  role: string;
  archived: boolean;
}) {
  const base = "/suppliers/" + sid + "/verification";
  const [config, setConfig] = useState<Config | null>(null),
    [runs, setRuns] = useState<Run[]>([]),
    [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(true),
    [error, setError] = useState("");
  const load = async () => {
    const [c, rs] = await Promise.all([
      request<Config>(base + "/policy"),
      request<Run[]>(base + "/runs"),
    ]);
    const current = rs.length
      ? await request<Result>(base + "/runs/" + rs[0].id)
      : null;
    setConfig(c);
    setRuns(rs);
    setResult(current);
  };
  async function action(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Verification unavailable.");
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    void action(load);
  }, [base]);
  const selected = result?.id === runs[0]?.id;
  const review = async (e: FormEvent<HTMLFormElement>, f: Finding) => {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    await action(async () => {
      await request(base + "/findings/" + f.id + "/review", "POST", {
        status: data.get("status"),
        reason: data.get("reason"),
        previous: f.history.at(-1)?.seq ?? 0,
      });
      await load();
    });
  };
  return (
    <section aria-label="Supplier verification">
      <h2>Verification workspace</h2>
      {error && (
        <p role="alert">
          {error} <button onClick={() => void action(load)}>Refresh</button>
        </p>
      )}
      {config && (
        <>
          <p>
            {config.version
              ? "Current policy v" + config.version
              : "No requirements configured"}
          </p>
          {role === "admin" && !archived && (
            <PolicyEditor
              key={config.version}
              config={config}
              busy={busy}
              save={(body) =>
                void action(async () => {
                  await request(
                    base + "/policy?previous=" + config.version,
                    "PUT",
                    body,
                  );
                  await load();
                })
              }
            />
          )}
          {role !== "auditor" && !archived && (
            <button
              disabled={busy || !config.version}
              onClick={() =>
                void action(async () => {
                  await request(base + "/runs", "POST");
                  await load();
                })
              }
            >
              Run verification
            </button>
          )}
        </>
      )}
      {busy && <p role="status">Loading verification…</p>}
      {!!runs.length && (
        <label>
          Verification history
          <select
            disabled={busy}
            value={result?.id ?? ""}
            onChange={(e) => {
              const id = e.target.value;
              void action(async () =>
                setResult(await request<Result>(base + "/runs/" + id)),
              );
            }}
          >
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                {r.as_of} UTC · policy v{r.policy_version} · {r.id.slice(0, 8)}
              </option>
            ))}
          </select>
        </label>
      )}
      {!result && !busy && <p>Not evaluated.</p>}
      {result && (
        <>
          <p role="status">
            {result.findings.some((f) => f.outcome === "conflict")
              ? "Conflict detected"
              : result.findings.some((f) => f.quality === "insufficient")
                ? "Insufficient evidence"
                : "No conflict detected in evaluated fields"}{" "}
            · {result.rule_version} · Policy v{result.policy_version}
          </p>
          <h3>Document checklist</h3>
          {!result.checklist.length && (
            <p>No required categories in this policy.</p>
          )}
          {result.checklist.map((r) => (
            <p key={r.category}>
              {r.category} · {label(r.outcome)}{" "}
              {r.expiry_check ? " · Expiry check enabled" : " · Expiry check inactive"} {r.when_type && " · type " + r.when_type}{" "}
              {r.when_jurisdiction && " · jurisdiction " + r.when_jurisdiction}
            </p>
          ))}
          <Evidence refs={result.inventory} />
          <h3>Findings</h3>
          {result.findings.map((f) => (
            <article key={f.id} className="vp-finding">
              <h4>
                {label(f.rule)} · {label(f.outcome)}
              </h4>
              <p>
                {f.severity} severity · {label(f.status)}
              </p>
              <p>{f.explanation}</p>
              <Evidence
                refs={f.evidence}
                sourcePath={base + "/findings/" + f.id + "/sources"}
              />
              {f.history.map((h) => (
                <p key={h.seq}>
                  {label(h.status)} · {h.reason} · {h.actor} ·{" "}
                  {new Date(h.created_at).toLocaleString()}
                </p>
              ))}
              {selected &&
                !archived &&
                ["admin", "reviewer"].includes(role) &&
                f.requires_review &&
                !["resolved", "dismissed"].includes(f.status) && (
                  <form onSubmit={(e) => void review(e, f)}>
                    <label>
                      Review action
                      <select name="status">
                        <option value="acknowledged">Acknowledge</option>
                        <option value="clarification_requested">
                          Request clarification
                        </option>
                        <option value="dismissed">Dismiss</option>
                        <option value="resolved">Resolve</option>
                      </select>
                    </label>
                    <label>
                      Reason or supporting information
                      <input name="reason" required maxLength={500} />
                    </label>
                    <button disabled={busy}>Record review</button>
                  </form>
                )}
            </article>
          ))}
        </>
      )}
    </section>
  );
}
