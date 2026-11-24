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

const steps = [
  {
    id: "dashboard",
    label: "Dashboard",
    instruction:
      "Sign in to your local workspace, then choose Suppliers → Create supplier.",
    alt: "Local dashboard with Suppliers and Exceptions in the sidebar",
  },
  {
    id: "upload",
    label: "Upload a PDF",
    instruction:
      "Open the supplier, go to Documents, choose a sample PDF and select Upload PDF.",
    alt: "Local supplier page with the document picker and verification controls",
  },
  {
    id: "extraction",
    label: "Inspect extraction",
    instruction:
      "When processing says Needs review, select View extraction 1 and check the candidate fields against the source.",
    alt: "Local Documents panel showing an insurance extraction and its source evidence",
  },
  {
    id: "verification",
    label: "Review findings",
    instruction:
      "Choose Configure requirements, save the policy and select Run verification. Open Findings to inspect evidence and decide how to follow up.",
    alt: "Local Verification workspace showing a saved policy, run history and document checklist",
  },
];

function WorkflowTour({ stepId }: { stepId: string | null }) {
  const current = steps.find(({ id }) => id === stepId) ?? steps[0];

  return (
    <section aria-labelledby="demo-tour">
      <h2 id="demo-tour">Walk through the local app</h2>
      <p>
        Choose a step to see a screenshot from a local test with synthetic data.
      </p>
      <nav aria-label="Local workflow steps">
        {steps.map(({ id, label }, index) => (
          <Link
            key={id}
            to={`?step=${id}#demo-tour`}
            className={id === current.id ? "active" : undefined}
            aria-current={id === current.id ? "step" : undefined}
          >
            {index + 1}. {label}
          </Link>
        ))}
      </nav>
      <figure className="demo-preview">
        <figcaption>{current.instruction}</figcaption>
        <a href={`/demo/${current.id}.jpg`}>
          <img
            src={`/demo/${current.id}.jpg`}
            alt={current.alt}
            width={1280}
            height={844}
          />
        </a>
      </figure>
    </section>
  );
}

export function PublicDemo() {
  const [params] = useSearchParams();
  const current =
    examples.find(({ id }) => id === params.get("case")) ?? examples[0];

  return (
    <main className="public-demo">
      <strong>VendorProof AI</strong>
      <h1>Public Demo Mode</h1>
      <p>Explore the local workflow or try a fictional supplier comparison.</p>
      <WorkflowTour stepId={params.get("step")} />
      <h2 id="sample-cases">Try a sample comparison</h2>
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
            to={{
              pathname: "/demo",
              search: "?case=" + id,
              hash: "#sample-cases",
            }}
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
