import { useState, type FormEvent } from "react";
import {
  Form,
  Link,
  useLoaderData,
  useOutletContext,
  useRevalidator,
  useSearchParams,
} from "react-router-dom";
import { api } from "./workspace";

type Member = { id: string; email: string };
type Item = {
  id: string;
  supplier_id: string;
  supplier: string;
  archived: boolean;
  run_id: string;
  rule: string;
  outcome: string;
  severity: string;
  created_at: string;
  status: string;
  owner: string | null;
  assignee: string | null;
  revision: number;
};
type Evidence = {
  document: string;
  digest: string;
  attempt: string | null;
  page?: number;
  field?: string;
  segment?: number;
  method?: string;
};
type Saved = {
  subject: string;
  message: string;
  revision: number;
  created_at: string;
  actor: string;
};
type Version = {
  document_id: string;
  replaces: string | null;
  state: string;
  archived: boolean;
  attempt: string;
  error_code: string | null;
  actor: string;
  created_at: string;
};
type Detail = Item & {
  guidance: {
    why: string;
    action: string;
    subjects: string[];
    sentences: string[];
    subject: string;
    message: string;
  };
  evidence: Evidence[];
  can_edit: boolean;
  transitions: string[];
  drafts: Saved[];
  corrections: Version[];
  replacement_targets: string[];
  history: {
    seq: number;
    kind: string;
    from_state: string | null;
    status: string;
    reason?: string;
    assigned_to: string | null;
    actor_name: string;
    created_at: string;
    compared_run: string | null;
    correction_doc: string | null;
  }[];
  comparison: {
    compared_run: string;
    correction_doc: string;
    current: {
      id: string;
      outcome: string;
      evidence: Evidence[];
      requires_review: boolean;
    }[];
  } | null;
  page: number;
};
const states = [
  "open",
  "assigned",
  "in_progress",
  "awaiting_supplier_response",
  "awaiting_internal_review",
  "resolved",
  "dismissed",
  "reopened",
];
const label = (s: string) => s.replaceAll("_", " ");
const date = (s: string) => new Date(s).toLocaleString();
const closed = (s: string) => ["resolved", "dismissed"].includes(s);
const options = (xs: string[]) =>
  xs.map((x) => (
    <option key={x} value={x}>
      {label(x)}
    </option>
  ));
function MemberSelect({
  members,
  name,
  initial,
  queue = false,
}: {
  members: Member[];
  name: string;
  initial: string;
  queue?: boolean;
}) {
  const [list, setList] = useState(members),
    [term, search] = useState(""),
    [error, setError] = useState(false);
  return (
    <>
      <label>
        {queue ? "Ownership" : "Assign to"}
        <select
          aria-label={queue ? "Ownership" : "Assign to"}
          key={initial}
          name={name}
          defaultValue={initial}
        >
          {queue ? (
            options(["all", "mine", "unassigned"])
          ) : (
            <option value="">Unassigned</option>
          )}
          {initial &&
            !["all", "mine", "unassigned"].includes(initial) &&
            !list.some((m) => m.id === initial) && (
              <option value={initial}>Current owner</option>
            )}
          {list.map((m) => (
            <option key={m.id} value={m.id}>
              {m.email}
            </option>
          ))}
        </select>
      </label>
      {(members.length === 100 || term) && (
        <>
          <label>
            Member email search
            <input value={term} onChange={(e) => search(e.target.value)} />
          </label>
          <button
            type="button"
            onClick={async () => {
              try {
                setList(
                  await api(
                    "/exceptions/members?q=" + encodeURIComponent(term),
                  ),
                );
                setError(false);
              } catch {
                setError(true);
              }
            }}
          >
            Find members
          </button>
          {error && <p role="alert">Member search failed.</p>}
        </>
      )}
    </>
  );
}
export function Queue() {
  const { data, members } = useLoaderData() as {
    data: {
      items: Item[];
      counts: { total: number; mine: number; unassigned: number };
      page: number;
    };
    members: Member[];
  };
  const [params] = useSearchParams();
  const value = (key: string, fallback: string) => params.get(key) || fallback;
  const pageLink = (n: number) => {
    const copy = new URLSearchParams(params);
    copy.set("page", String(n));
    return "?" + copy;
  };
  return (
    <>
      <h1>Exception queue</h1>
      <section>
        <Form className="filters" method="get" key={params.toString()}>
          <label>
            Supplier name
            <input name="q" defaultValue={value("q", "")} maxLength={160} />
          </label>
          <MemberSelect
            members={members}
            queue
            name="owner"
            initial={value("owner", "all")}
          />
          <label>
            Severity
            <select name="severity" defaultValue={value("severity", "all")}>
              {options(["all", "high", "medium", "low"])}
            </select>
          </label>
          <label>
            Resolution status
            <select name="status" defaultValue={value("status", "unresolved")}>
              {options(["unresolved", "all", ...states])}
            </select>
          </label>
          <label>
            Minimum age in days
            <input
              name="age"
              type="number"
              min="0"
              max="36500"
              defaultValue={value("age", "0")}
            />
          </label>
          <label>
            Sort by
            <select name="sort" defaultValue={value("sort", "severity")}>
              {options(["severity", "age", "supplier", "status"])}
            </select>
          </label>
          <button>Apply filters</button>
        </Form>
        <p>
          {data.counts.total} matching · {data.counts.mine} assigned to me ·{" "}
          {data.counts.unassigned} unassigned
        </p>
        {data.items.length === 0 ? (
          <p>No exceptions match these filters.</p>
        ) : (
          data.items.map((i) => (
            <article className="vp-finding" key={i.id}>
              <h2>
                <Link to={i.id}>
                  {i.supplier} · {label(i.rule)}
                </Link>
              </h2>
              <p>
                {label(i.outcome)} · {i.severity} severity · {label(i.status)}
              </p>
              <p>
                {i.owner || "Unassigned"} · Opened {date(i.created_at)} ·{" "}
                {Math.max(
                  0,
                  Math.floor(
                    (Date.now() - Date.parse(i.created_at)) / 86400000,
                  ),
                )}{" "}
                days old{i.archived ? " · Archived supplier" : ""}
              </p>
            </article>
          ))
        )}
        <footer>
          {data.page > 1 && <Link to={pageLink(data.page - 1)}>Previous</Link>}
          Page {data.page}
          {data.page * 20 < data.counts.total && (
            <Link to={pageLink(data.page + 1)}>Next</Link>
          )}
        </footer>
      </section>
    </>
  );
}
function Sources({
  refs,
  sourcePath,
}: {
  refs: Evidence[];
  sourcePath?: string;
}) {
  const [span, setSpan] = useState("");
  async function inspect(index: number) {
    try {
      const result = await api(sourcePath + "/" + index);
      setSpan("Page " + result.page + " · " + result.excerpt);
    } catch {
      setSpan("This source is unavailable.");
    }
  }
  return (
    <>
      {refs.length ? (
        refs.map((r, i) => (
          <p className="vp-source" key={i}>
            Document {r.document} · SHA-256 {r.digest}
            {r.page && " · page " + r.page}
            {r.field && " · " + label(r.field)}
            {r.segment !== undefined && " · segment " + r.segment}
            {r.method && " · " + r.method}
            {r.attempt && " · attempt " + r.attempt}
            {sourcePath && r.segment !== undefined && (
              <button onClick={() => void inspect(i)}>
                Inspect cited span
              </button>
            )}
          </p>
        ))
      ) : (
        <p>No source document cited.</p>
      )}
      {span && <p role="status">{span}</p>}
    </>
  );
}
type Submit = (
  action: () => Promise<unknown>,
  success: string,
) => Promise<void>;
function DraftEditor({
  d,
  submit,
  busy,
}: {
  d: Detail;
  submit: Submit;
  busy: boolean;
}) {
  const saved = d.drafts[0] || d.guidance;
  const [subject, setSubject] = useState(saved.subject),
    [message, setMessage] = useState(saved.message);
  const lines = message.split("\n");
  const valid =
    lines.includes(d.guidance.action) &&
    lines.length === new Set(lines).size &&
    lines.every((line) => d.guidance.sentences.includes(line));
  return (
    <section>
      <h2>Correction request</h2>
      <p>
        Select a subject and edit the message using the approved sentences
        below. Include the requested action.
      </p>
      <label>
        Draft subject
        <select value={subject} onChange={(e) => setSubject(e.target.value)}>
          {options(d.guidance.subjects)}
        </select>
      </label>
      <label>
        Draft message
        <textarea
          rows={5}
          maxLength={1200}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
        />
      </label>
      {d.guidance.sentences.map((line) => (
        <button
          key={line}
          type="button"
          disabled={message.split("\n").includes(line)}
          onClick={() => setMessage(message ? message + "\n" + line : line)}
        >
          {line}
        </button>
      ))}
      <h3>Supplier-facing preview</h3>
      <strong>{subject}</strong>
      {valid ? (
        <p className="vp-preview">{message}</p>
      ) : (
        <p role="alert">
          Use each approved sentence at most once and include the requested
          action.
        </p>
      )}
      <button
        disabled={busy || !valid}
        onClick={() =>
          void submit(
            () =>
              post(d.id, "drafts", {
                subject,
                message,
                previous: d.drafts[0]?.revision || 0,
              }),
            "Draft saved",
          )
        }
      >
        Save draft
      </button>
    </section>
  );
}
const post = (id: string, action: string, body: object) =>
  api("/exceptions/" + id + "/" + action, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
export function ExceptionDetail() {
  const { d, members } = useLoaderData() as { d: Detail; members: Member[] };
  const { role } = useOutletContext<{ role: string }>();
  const refresh = useRevalidator();
  const [notice, setNotice] = useState(""),
    [failure, setFailure] = useState(""),
    [busy, setBusy] = useState(false);
  const submit: Submit = async (action, msg) => {
    setBusy(true);
    setFailure("");
    setNotice("");
    try {
      await action();
      await refresh.revalidate();
      setNotice(msg);
    } catch (e) {
      setFailure(
        e instanceof Response && e.status === 409
          ? "The record changed or the action is unavailable. Refresh and check the latest evidence."
          : "The request failed. Check your access and form values.",
      );
    } finally {
      setBusy(false);
    }
  };
  const [requestId, setRequestId] = useState(() => crypto.randomUUID());
  const mutable = !d.archived && d.page === 1,
    open = mutable && !closed(d.status),
    base = "/suppliers/" + d.supplier_id;
  const latest = d.corrections[0];
  const pending = busy || refresh.state !== "idle";
  const form = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    return new FormData(e.currentTarget);
  };
  return (
    <>
      <Link to="/exceptions">Exception queue</Link>
      <h1>
        {label(d.rule)} · {label(d.outcome)}
      </h1>
      <p>
        <Link to={base}>{d.supplier}</Link> · {d.severity} severity ·{" "}
        {label(d.status)} · {d.owner || "Unassigned"}
      </p>
      <button disabled={pending} onClick={() => void refresh.revalidate()}>
        Refresh exception
      </button>
      {notice && <p role="status">{notice}</p>}
      {failure && <p role="alert">{failure}</p>}
      <section>
        <h2>Corrective guidance</h2>
        <p>{d.guidance.why}</p>
        <strong>{d.guidance.action}</strong>
        <details>
          <summary>Original evidence ({d.evidence.length})</summary>
          <p>Verification run {d.run_id}</p>
          <Sources
            key={d.id + "-" + d.revision + "-" + d.corrections[0]?.document_id}
            refs={d.evidence}
            sourcePath={
              role === "admin"
                ? base + "/verification/findings/" + d.id + "/sources"
                : undefined
            }
          />
        </details>
      </section>
      {open && role === "admin" && (
        <section>
          <h2>Ownership</h2>
          <form
            onSubmit={(e) => {
              const f = form(e);
              void submit(
                () =>
                  post(d.id, "assignment", {
                    previous: d.revision,
                    assignee: f.get("assignee") || null,
                    reason: f.get("reason"),
                  }),
                "Assignment recorded",
              );
            }}
          >
            <MemberSelect
              name="assignee"
              initial={d.assignee || ""}
              members={members}
            />
            <label>
              Assignment reason
              <input required name="reason" maxLength={500} />
            </label>
            <button disabled={pending}>Record assignment</button>
          </form>
        </section>
      )}
      {open && d.can_edit && (
        <DraftEditor
          key={d.id + "-" + d.drafts[0]?.revision}
          d={d}
          submit={submit}
          busy={pending}
        />
      )}
      {d.drafts.length > 0 && (
        <section>
          <h2>Saved drafts</h2>
          {d.drafts.map((v) => (
            <details key={v.revision}>
              <summary>
                Revision {v.revision} · {date(v.created_at)}
              </summary>
              <p>{v.subject}</p>
              <p className="vp-preview">{v.message}</p>
              <p>Author {v.actor}</p>
            </details>
          ))}
        </section>
      )}
      <section>
        <h2>Corrected documents</h2>
        {!latest && <p>No linked versions on this page.</p>}
        {d.corrections.map((v) => (
          <p className="vp-source" key={v.document_id}>
            {v.document_id} · {label(v.state)}
            {v.archived && " · archived"} · {date(v.created_at)} · uploaded by{" "}
            {v.actor}
            {v.error_code && " · " + v.error_code}
          </p>
        ))}
        {open && ["admin", "operator"].includes(role) && (
          <form
            onSubmit={(e) => {
              const f = form(e),
                file = f.get("file") as File;
              const p = new URLSearchParams({
                finding_id: d.id,
                request_id: requestId,
              });
              if (f.get("replaces"))
                p.set("replaces", String(f.get("replaces")));
              void submit(async () => {
                await api(base + "/documents?" + p, {
                  method: "POST",
                  headers: {
                    "Content-Type": "application/pdf",
                    "X-Filename": file.name,
                  },
                  body: file,
                });
                setRequestId(crypto.randomUUID());
              }, "Correction queued");
            }}
          >
            <label>
              Document to replace
              <select name="replaces">
                {d.replacement_targets.length ? (
                  d.replacement_targets.map((id) => (
                    <option key={id} value={id}>
                      {id}
                    </option>
                  ))
                ) : (
                  <option value="">Add supporting document</option>
                )}
              </select>
            </label>
            <label>
              Corrected PDF
              <input
                name="file"
                type="file"
                accept="application/pdf"
                required
              />
            </label>
            <label>
              <input type="checkbox" required />
              Confirm corrected version
            </label>
            <button disabled={pending}>Upload correction</button>
          </form>
        )}
        {open &&
          latest?.state === "failed" &&
          !latest.archived &&
          ["admin", "operator"].includes(role) && (
            <button
              disabled={pending}
              onClick={() =>
                void submit(
                  () =>
                    api(
                      base +
                        "/documents/" +
                        latest.document_id +
                        "/processing?after=" +
                        latest.attempt,
                      { method: "POST" },
                    ),
                  "Retry queued",
                )
              }
            >
              Retry extraction
            </button>
          )}
        {open &&
          d.can_edit &&
          latest &&
          !latest.archived &&
          ["needs_review", "failed"].includes(latest.state) && (
            <button
              disabled={pending}
              onClick={() =>
                void submit(
                  () => post(d.id, "compare", { previous: d.revision }),
                  "Verification compared",
                )
              }
            >
              Rerun and compare
            </button>
          )}
      </section>
      {d.comparison && (
        <section>
          <h2>Verification comparison</h2>
          <p>Original outcome · {label(d.outcome)}</p>
          <p>Compared run {d.comparison.compared_run}</p>
          {d.comparison.current.length ? (
            d.comparison.current.map((r) => (
              <div key={r.id}>
                <strong>Current outcome · {label(r.outcome)}</strong>
                <Sources
                  refs={r.evidence}
                  sourcePath={
                    role === "admin"
                      ? base + "/verification/findings/" + r.id + "/sources"
                      : undefined
                  }
                />
              </div>
            ))
          ) : (
            <p>No comparable finding supplies supporting evidence.</p>
          )}
        </section>
      )}
      {mutable && d.transitions.length > 0 && (
        <section>
          <h2>Human decision</h2>
          <form
            key={d.revision}
            onSubmit={(e) => {
              const f = form(e);
              void submit(
                () =>
                  post(d.id, "decision", {
                    previous: d.revision,
                    status: f.get("status"),
                    reason: f.get("reason"),
                    reviewed_run: d.comparison?.compared_run || null,
                  }),
                "Decision recorded",
              );
            }}
          >
            <label>
              Next state<select name="status">{options(d.transitions)}</select>
            </label>
            <label>
              Decision reason
              <input required maxLength={500} name="reason" />
            </label>
            <label>
              <input required type="checkbox" />I reviewed the available
              evidence and confirm this decision
            </label>
            <button disabled={pending}>Record decision</button>
          </form>
        </section>
      )}
      <section>
        <h2>Review history</h2>
        {d.history.length === 0 && <p>No review events on this page.</p>}
        {d.history.map((h) => (
          <article className="vp-finding" key={h.seq}>
            <strong>
              {label(h.kind)} · {label(h.from_state || "prior review")} →{" "}
              {label(h.status)}
            </strong>
            <p>
              {h.actor_name} · {date(h.created_at)}
              {h.kind === "assignment" &&
                " · " + (h.assigned_to || "Unassigned")}
            </p>
            <p>{h.reason}</p>
            {h.compared_run && (
              <p>
                Run {h.compared_run} · Document {h.correction_doc}
              </p>
            )}
          </article>
        ))}
      </section>
      <footer>
        {d.page > 1 && <Link to={"?page=" + (d.page - 1)}>Newer history</Link>}
        {Math.max(d.history.length, d.drafts.length, d.corrections.length) ===
          20 && <Link to={"?page=" + (d.page + 1)}>Older history</Link>}
      </footer>
    </>
  );
}
