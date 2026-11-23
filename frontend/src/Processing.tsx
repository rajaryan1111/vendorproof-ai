import { useEffect, useState } from "react";
import { apiBase } from "./api";

type Attempt = {
  id: string;
  attempt: number;
  state: string;
  error_code: string | null;
  category: string | null;
  pages: number | null;
  candidate_count: number;
};
type Source = {
  page: number;
  segment: number;
  start: number;
  end: number;
  original: string;
  method: string;
};
type Report = {
  document_id: string;
  version_digest: string;
  schema_version: string;
  implementation: string;
  classification: { category: string; status: string; evidence: Source[] };
  pages: {
    number: number;
    warning: string | null;
    segments: {
      method: string;
      text: string;
      bbox: number[] | null;
      confidence: number | null;
    }[];
    words: number;
  }[];
  candidates: {
    key: string;
    value: string | null;
    normalized: string | null;
    status: string;
    alternatives?: Source[];
    source: Source | null;
  }[];
};
async function request(path: string, method = "GET") {
  const r = await fetch(apiBase + path, {
    method,
    credentials: "include",
    cache: "no-store",
    headers: { "X-VP-Request": "1" },
  });
  if (!r.ok) throw Error("Request failed");
  return r.json();
}
export function Evidence({ report }: { report: Report }) {
  const c = report.classification;
  return (
    <section aria-label="Extraction report">
      <h3>Extraction candidates</h3>
      <p>
        {c.category} · {c.status} · Needs human review
      </p>
      {c.evidence.map((s, i) => (
        <p key={i}>
          Classification evidence · page {s.page}: {s.original}
        </p>
      ))}
      <p>
        Schema {report.schema_version} · {report.implementation}
      </p>
      <dl>
        {report.candidates.map((f) => (
          <div key={f.key}>
            <dt>{f.key.replaceAll("_", " ")}</dt>
            <dd>
              {f.value ?? "Unresolved"} · {f.status}
              {f.alternatives?.map((r, i) => (
                <small key={i}>
                  {" "}
                  · Page {r.page} ({r.method}): {r.original}
                </small>
              ))}
              {f.source && (
                <small>
                  {" "}
                  · Page {f.source.page}, segment {f.source.segment + 1},
                  characters {f.source.start}–{f.source.end} ({f.source.method})
                </small>
              )}
            </dd>
          </div>
        ))}
      </dl>
      {report.pages.map((p) => (
        <details key={p.number}>
          <summary>
            Page {p.number} · {p.words} words{" "}
            {p.warning && "· " + p.warning.replaceAll("_", " ")}
          </summary>
          {p.segments.map((s, i) => (
            <div key={i}>
              <strong>
                Segment {i + 1} · {s.method}
              </strong>
              {s.confidence !== null && (
                <small>
                  {" "}
                  · OCR engine confidence {s.confidence.toFixed(1)}/100
                </small>
              )}
              <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
                {s.text}
              </pre>
            </div>
          ))}
        </details>
      ))}
    </section>
  );
}
export function Processing({
  path,
  editable,
  restricted, reviewer,
}: {
  path: string;
  editable: boolean;
  restricted: boolean; reviewer: boolean;
}) {
  const [history, setHistory] = useState<Attempt[] | null>(null);
  const [revision, setRevision] = useState(0);
  const [summary,setSummary]=useState<{fields:{key:string;status:string;pages:number[]}[];pages:{number:number;warning:string|null}[]}|null>(null);
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const rows: Attempt[] = await request(path);
        if (!live) return;
        setHistory(rows);
        setError("");
        if (["queued", "processing"].includes(rows[0]?.state))
          timer = setTimeout(load, 2000);
      } catch {
        if (live) setError("Could not load processing history.");
      }
    }
    void load();
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [path, revision]);
  const last = history?.[0];
  async function act(read?: Attempt) {
    setBusy(true);
    setError("");
    try {
      if(read && reviewer) setSummary(await request(path+"/"+read.id+"?summary=true"));
      else if (read) setReport(await request(path + "/" + read.id));
      else {
        await request(path + (last ? "?after=" + last.id : ""), "POST");
        setReport(null);
        setRevision((x) => x + 1);
      }
    } catch {
      setError("Request failed. Check your session and permissions.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div>
      <p role="status">
        Processing ·{" "}
        {history === null
          ? "Loading…"
          : (last?.state ?? "uploaded").replaceAll("_", " ")}
      </p>
      {editable &&
        history !== null &&
        !["queued", "processing"].includes(last?.state ?? "") && (
          <button disabled={busy} onClick={() => void act()}>
            {last ? "Reprocess" : "Process PDF"}
          </button>
        )}
      {error && (
        <p role="alert">
          {error}{" "}
          <button onClick={() => setRevision((x) => x + 1)}>Refresh</button>
        </p>
      )}
      {history?.map((a) => (
        <div key={a.id}>
          Attempt {a.attempt} · {a.state.replaceAll("_", " ")} {a.error_code}
          {a.category && (
            <p>
              Suggested class: {a.category} · {a.pages} pages ·{" "}
              {a.candidate_count} candidates
            </p>
          )}
          {(!restricted || reviewer) && a.state === "needs_review" && (
            <button disabled={busy} onClick={() => void act(a)}>
              View extraction {a.attempt}
            </button>
          )}
        </div>
      ))}
      {summary && <section><h3>Review details</h3>{summary.fields.map(f=><p key={f.key}>{f.key.replaceAll("_"," ")} · {f.status}{f.pages.length>0 && " · Page "+f.pages.join(", ")}</p>)}{summary.pages.filter(p=>p.warning).map(p=><p key={p.number}>Page {p.number} · {p.warning}</p>)}</section>}
      {report && <Evidence report={report} />}
    </div>
  );
}
