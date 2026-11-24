import {
  Form,
  Link,
  useActionData,
  useLoaderData,
  useNavigation,
  type ActionFunctionArgs,
} from "react-router-dom";
import { api } from "./workspace";

type Member = {
  id: string;
  email: string;
  role: string;
  active: boolean;
  own: boolean;
};
export async function changeAccess({ request }: ActionFunctionArgs) {
  const data = await request.formData();
  try {
    await api("/organization/members/" + data.get("id"), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        role: data.get("role"),
        active: data.get("status") === "active",
        previous_role: data.get("previous_role"),
        previous_active: data.get("previous_active") === "true",
      }),
    });
    return { ok: true, message: "Access settings saved." };
  } catch (err) {
    if (err instanceof Response && err.status === 302) throw err;
    return {
      ok: false,
      message:
        err instanceof Response && err.status === 409
          ? "Another administrator changed this member. Review the current settings and try again."
          : "Could not update member access. Refresh the workspace and try again.",
    };
  }
}

export function Organization() {
  const { members, more, page } = useLoaderData() as {
    members: Member[];
    more: boolean;
    page: number;
  };
  const result = useActionData() as
    { ok: boolean; message: string } | undefined;
  const navigation = useNavigation();
  return (
    <>
      <h1>Organization</h1>
      <section>
        <h2>Workspace members</h2>
        <p>
          Role or access changes end the member’s current sessions. New accounts
          are provisioned by the deployment operator.
        </p>
        {result && (
          <p role={result.ok ? "status" : "alert"}>{result.message}</p>
        )}
        {members.map((m) => (
          <article className="member-row" key={m.id + m.role + m.active}>
            <div>
              <strong>{m.email}</strong>
              <p>
                {m.role} · {m.active ? "Active" : "Suspended"}
                {m.own && " · Your account"}
              </p>
            </div>
            {!m.own && (
              <details>
                <summary>Edit access</summary>
                <Form
                  method="post"
                  onSubmit={(e) => {
                    if (
                      !window.confirm(
                        "Save access changes for " + m.email + "?",
                      )
                    )
                      e.preventDefault();
                  }}
                >
                  <input type="hidden" name="id" value={m.id} />
                  <input type="hidden" name="previous_role" value={m.role} />
                  <input
                    type="hidden"
                    name="previous_active"
                    value={String(m.active)}
                  />
                  <label>
                    Role
                    <select name="role" defaultValue={m.role}>
                      {["admin", "operator", "reviewer", "auditor"].map((r) => (
                        <option key={r}>{r}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Access
                    <select
                      name="status"
                      defaultValue={m.active ? "active" : "suspended"}
                    >
                      <option value="active">Active</option>
                      <option value="suspended">Suspended</option>
                    </select>
                  </label>
                  <button disabled={navigation.state !== "idle"}>
                    Save access
                  </button>
                </Form>
              </details>
            )}
          </article>
        ))}
        {(page > 1 || more) && (
          <footer>
            {page > 1 && <Link to={"?page=" + (page - 1)}>Previous</Link>}Page{" "}
            {page}
            {more && <Link to={"?page=" + (page + 1)}>Next</Link>}
          </footer>
        )}
      </section>
    </>
  );
}
