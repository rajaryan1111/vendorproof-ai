import { Link, NavLink, useSearchParams } from "react-router-dom";

const examples = [
  {
    id: "matching",
    title: "Matching names",
    registration: "Orchid Ltd",
    tax: "Orchid Ltd",
    finding: "Exact match",
    next: "Review the rest of the requirements before making a supplier decision.",
  },
  {
    id: "alias",
    title: "Different legal suffixes",
    registration: "Orchid Pvt Ltd",
    tax: "Orchid Private Limited",
    finding: "Normalized match",
    next: "Check whether your policy allows these legal suffixes to be treated as equivalent.",
  },
  {
    id: "conflict",
    title: "Conflicting names",
    registration: "Orchid Limited",
    tax: "Flint Limited",
    finding: "Name conflict",
    next: "Check which record is correct and request a correction if needed.",
  },
];

export function PublicDemo() {
  const [params] = useSearchParams();
  const current =
    examples.find(({ id }) => id === params.get("case")) ?? examples[0];

  return (
    <main className="public-demo">
      <strong>VendorProof AI</strong>
      <h1>Public Demo Mode</h1>
      <p>
        Compare company names from two sample records and see how a reviewer
        would follow up.
      </p>
      <p>
        These examples use fictional records and prewritten findings. No
        verification or OCR runs here.
      </p>
      <nav aria-label="Sample cases">
        {examples.map(({ id, title }) => (
          <Link
            key={id}
            to={{ pathname: "/demo", search: "?case=" + id }}
            className={id === current.id ? "active" : undefined}
            aria-current={id === current.id ? "true" : undefined}
          >
            {title}
          </Link>
        ))}
      </nav>
      <section aria-labelledby="demo-case">
        <h2 id="demo-case">{current.title}</h2>
        <dl className="availability-checks">
          <div>
            <dt>Company registration · legal name</dt>
            <dd>{current.registration}</dd>
          </div>
          <div>
            <dt>Tax registration · registered name</dt>
            <dd>{current.tax}</dd>
          </div>
        </dl>
        <h3>Example finding</h3>
        <p>
          <strong>{current.finding}</strong>
        </p>
        <h3>Reviewer follow-up</h3>
        <p>{current.next}</p>
      </section>
      <footer>
        <p>The public demo has no accounts, uploads, or private records.</p>
        <NavLink to="/login">Hosted service status</NavLink>
      </footer>
    </main>
  );
}
