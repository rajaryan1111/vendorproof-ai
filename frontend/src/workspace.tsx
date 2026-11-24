import {
  Form,
  Link,
  NavLink,
  Outlet,
  redirect,
  useActionData,
  useLoaderData,
  useNavigation,
  useOutletContext,
  useRouteError,
  type ActionFunctionArgs,
} from "react-router-dom";
import { apiBase, readHealth } from "./api";
import { Verification } from "./Verification";
import { Processing } from "./Processing";
import { Dashboard } from "./Dashboard";

type Account = { email: string; role: string; workspace: string };
type Supplier = {
  id: string;
  name: string;
  contact: string;
  archived: boolean;
  updated_at: string;
};
type Doc = { id: string; filename: string; bytes: number; status: string };
type Overview = {
  total: number;
  active: number;
  archived: number;
  documents: number;
  needs_review: number;
  verification_pending: number;
  recent: { action: string; name: string; created_at: string }[];
};

export async function api(path: string, init?: RequestInit) {
  const res = await fetch(apiBase + path, {
    ...init,
    credentials: "include",
    cache: "no-store",
    headers: { "X-VP-Request": "1", ...init?.headers },
  });
  if (res.status === 401 && path != "/login") throw redirect("/login");
  if (!res.ok) throw new Response(null, { status: res.status });
  return res.json();
}
export function Failure() {
  const error = useRouteError() as { status?: number };
  if (!error?.status || error.status >= 500) return <Offline />;
  return (
    <main className="login">
      <h1>Request unavailable</h1>
      <p role="alert">
        {error?.status === 403
          ? "Your role does not permit this action."
          : "Check your connection and the requested record."}
      </p>
      <Link to="/">Return to dashboard</Link>
    </main>
  );
}
function Feedback() {
  const error = useActionData() as string | undefined;
  return error ? <p role="alert">{error}</p> : null;
}
function Submit({ children }: { children: string }) {
  const nav = useNavigation();
  return <button disabled={nav.state !== "idle"}>{children}</button>;
}
export async function signInAvailable() {
  try {
    await readHealth(AbortSignal.timeout(10000), true);
    return true;
  } catch {
    return false;
  }
}

function Offline() {
  return (
    <main className="login">
      <section>
        <strong>VendorProof AI</strong>
        <h1>Workspace offline</h1>
        <p>
          Sign-in and document intake are unavailable until the secure workspace
          is connected.
        </p>
        <Link to="/login" reloadDocument>
          Check connection again
        </Link>
      </section>
    </main>
  );
}

export function Login() {
  if (!useLoaderData()) return <Offline />;
  return (
    <main className="login">
      <section>
        <strong>VendorProof AI</strong>
        <h1>Sign in</h1>
        <Form method="post">
          <label>
            Workspace
            <input
              name="workspace"
              autoComplete="organization"
              required
              maxLength={160}
            />
          </label>
          <label>
            Email
            <input name="email" type="email" autoComplete="username" required />
          </label>
          <label>
            Password
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              required
            />
          </label>
          <Feedback />
          <Submit>Sign in</Submit>
        </Form>
      </section>
    </main>
  );
}
export async function signIn({ request }: ActionFunctionArgs) {
  const fields = Object.fromEntries(await request.formData());
  try {
    await api("/login", json("POST", fields));
    return redirect("/");
  } catch (e) {
    return e instanceof Response && e.status === 401
      ? "Check your workspace, email and password."
      : "Sign-in unavailable. Try again later.";
  }
}
function json(method: string, body: unknown) {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}
export function Shell() {
  const user = useLoaderData() as Account;
  const nav = useNavigation();
  return (
    <>
      <a className="skip" href="#workspace">
        Skip to workspace
      </a>
      <aside>
        <strong>VendorProof AI</strong>
        <nav aria-label="Workspace navigation">
          <NavLink to="/" end>
            Dashboard
          </NavLink>
          <NavLink to="/exceptions">Exceptions</NavLink>
          <NavLink to="/suppliers">Suppliers</NavLink>
          {user.role === "admin" && (
            <NavLink to="/organization">Organization</NavLink>
          )}
        </nav>
      </aside>
      <main id="workspace" tabIndex={-1}>
        <header>
          <div className="account">
            <strong>{user.workspace}</strong>
            <span>
              {user.email} · {user.role}
            </span>
          </div>
          <Form method="post" action="/logout">
            <Submit>Sign out</Submit>
          </Form>
        </header>
        <div role="status">{nav.state !== "idle" ? "Loading…" : ""}</div>
        <Outlet context={user} />
      </main>
    </>
  );
}
export function Home() {
  const data = useLoaderData() as Overview;
  return (
    <>
      <h1>Dashboard</h1>
      <div className="metrics">
        {(
          [
            "total",
            "active",
            "archived",
            "documents",
            "needs_review",
            "verification_pending",
          ] as const
        ).map((k) => (
          <section key={k}>
            <p>{k === "total" ? "Total suppliers" : k.replaceAll("_", " ")}</p>
            <strong>{data[k]}</strong>
          </section>
        ))}
      </div>
      <section>
        <h2>Recent supplier activity</h2>
        {data.recent.length ? (
          data.recent.map((r, i) => (
            <p key={i}>
              {r.action} · {r.name} · {new Date(r.created_at).toLocaleString()}
            </p>
          ))
        ) : (
          <p>No supplier activity yet.</p>
        )}
      </section>
      <details>
        <summary>Service connection</summary>
        <Dashboard />
      </details>
    </>
  );
}
function writable(role: string) {
  return role === "admin" || role === "operator";
}
export function Directory() {
  const { rows, q, archived, page } = useLoaderData() as {
    rows: Supplier[];
    q: string;
    archived: string;
    page: number;
  };
  const user = useOutletContext<Account>();
  const url = (n: number) =>
    "?" + new URLSearchParams({ q, archived, page: String(n) });
  return (
    <>
      <h1>Supplier directory</h1>
      {writable(user.role) && <Link to="new">Create supplier</Link>}
      <Form className="filters" key={q + archived}>
        <label>
          Search suppliers
          <input name="q" defaultValue={q} />
        </label>
        <label>
          Status
          <select name="archived" defaultValue={archived}>
            <option value="false">Active</option>
            <option value="true">Archived</option>
          </select>
        </label>
        <button>Filter</button>
      </Form>
      <section>
        {rows.length ? (
          <table>
            <thead>
              <tr>
                <th>Supplier</th>
                <th>Contact</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((s) => (
                <tr key={s.id}>
                  <td>
                    <Link to={s.id}>{s.name}</Link>
                  </td>
                  <td>{s.contact || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p>No suppliers match this view.</p>
        )}
        <footer>
          {page > 1 && <Link to={url(page - 1)}>Previous</Link>} Page {page}{" "}
          {rows.length === 20 && <Link to={url(page + 1)}>Next</Link>}
        </footer>
      </section>
    </>
  );
}
export function Editor() {
  const s = useLoaderData() as Supplier | null;
  const user = useOutletContext<Account>();
  if (!writable(user.role))
    return <p>Editing requires a procurement operator or administrator.</p>;
  return (
    <>
      <h1>{s ? "Edit supplier" : "Create supplier"}</h1>
      <section>
        <Form method="post">
          <label>
            Supplier name
            <input
              name="name"
              required
              maxLength={160}
              defaultValue={s?.name}
            />
          </label>
          <label>
            Contact
            <input name="contact" maxLength={240} defaultValue={s?.contact} />
          </label>
          <Feedback />
          <Submit>Save supplier</Submit>
        </Form>
      </section>
    </>
  );
}
export async function save({ params, request }: ActionFunctionArgs) {
  const id = params.id;
  try {
    const s = await api(
      "/suppliers" + (id ? "/" + id : ""),
      json(id ? "PATCH" : "POST", Object.fromEntries(await request.formData())),
    );
    return redirect("/suppliers/" + s.id);
  } catch (e) {
    if (e instanceof Response && e.status === 302) throw e;
    return "Could not save the supplier. Check the fields and try again.";
  }
}
export function Detail() {
  const { s, docs, page } = useLoaderData() as {
    s: Supplier;
    docs: Doc[];
    page: number;
  };
  const user = useOutletContext<Account>();
  const edit = writable(user.role) && !s.archived;
  return (
    <>
      <Link to="/suppliers">Supplier directory</Link>
      <h1>{s.name}</h1>
      <section>
        <p>
          {s.archived ? "Archived" : "Active"} · Updated{" "}
          {new Date(s.updated_at).toLocaleDateString()}
        </p>
        <p>{s.contact || "No contact recorded"}</p>
        {edit && <Link to="edit">Edit supplier</Link>}
        {!s.archived && user.role === "admin" && (
          <Form
            method="post"
            onSubmit={(e) => {
              if (!confirm("Archive this supplier?")) e.preventDefault();
            }}
          >
            <button name="action" value="archive">
              Archive supplier
            </button>
          </Form>
        )}
      </section>
      <Verification
        key={s.id + user.role}
        sid={s.id}
        role={user.role}
        archived={s.archived}
      />
      <section>
        <h2>Documents</h2>
        <Feedback />
        {docs.length === 0 && <p>No documents on file.</p>}
        {docs.map((d) => (
          <div className="document-row" key={d.id}>
            <div>
              <strong>{d.filename}</strong>
              <p>
                {d.bytes} bytes · {d.status}
              </p>
            </div>
            {user.role === "admin" && (
              <a href={apiBase + "/suppliers/" + s.id + "/documents/" + d.id}>
                Download
              </a>
            )}
            {edit && (
              <Form
                method="post"
                onSubmit={(e) => {
                  if (!confirm("Archive this document?")) e.preventDefault();
                }}
              >
                <input type="hidden" name="key" value={d.id} />
                <button name="action" value="remove">
                  Archive document
                </button>
              </Form>
            )}
            <Processing
              path={"/suppliers/" + s.id + "/documents/" + d.id + "/processing"}
              editable={edit}
              restricted={user.role !== "admin"}
              reviewer={user.role === "reviewer"}
            />
          </div>
        ))}
        {(page > 1 || docs.length === 20) && (
          <footer>
            {page > 1 && (
              <Link to={"?documents=" + (page - 1)}>Previous documents</Link>
            )}
            Page {page}
            {docs.length === 20 && (
              <Link to={"?documents=" + (page + 1)}>More documents</Link>
            )}
          </footer>
        )}
        {edit && (
          <Form method="post" encType="multipart/form-data">
            <label>
              PDF document (up to 5 MiB)
              <input
                type="file"
                required
                name="file"
                accept="application/pdf,.pdf"
              />
            </label>
            {docs.length > 0 && (
              <label>
                Document version
                <select name="replaces">
                  <option value="">New document</option>
                  {docs.map((d) => (
                    <option key={d.id} value={d.id}>
                      Replace {d.filename}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <Submit>Upload PDF</Submit>
          </Form>
        )}
      </section>
    </>
  );
}
export async function manage({ params, request }: ActionFunctionArgs) {
  const data = await request.formData(),
    base = "/suppliers/" + params.id;
  try {
    if (data.get("action") === "archive") {
      await api(base, { method: "DELETE" });
      return redirect("/suppliers");
    }
    if (data.get("action") === "remove") {
      await api(base + "/documents/" + data.get("key"), { method: "DELETE" });
    } else {
      const file = data.get("file");
      if (!(file instanceof File) || file.size > 5 * 1024 * 1024)
        return "Select a PDF up to 5 MiB.";
      await api(
        base +
          "/documents" +
          (data.get("replaces")
            ? "?replaces=" + encodeURIComponent(String(data.get("replaces")))
            : ""),
        {
          method: "POST",
          headers: { "Content-Type": file.type, "X-Filename": file.name },
          body: file,
        },
      );
    }
    return redirect(base);
  } catch (e) {
    if (e instanceof Response && e.status === 302) throw e;
    return "Request failed. Check permissions and use a valid PDF with a plain filename.";
  }
}
