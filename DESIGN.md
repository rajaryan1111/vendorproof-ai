# VendorProof AI Product and UI Design

**Status:** Initial design system direction; validate through implementation and user feedback. Phase 1 implements sign-in, workspace and role display, dashboard counts and activity, a supplier directory, create/edit forms, detail pages and PDF version management. Dashboard service status supports retry.

## Principles

1. Evidence before conclusions: show what was found, where it came from, and what remains uncertain.
2. Calm operational clarity: prioritize work state, next action, and exceptions over decorative metrics.
3. Human control: make review and approval actions explicit, attributable, and reversible only through a recorded follow-up.
4. Information density with legibility: support side-by-side documents and fields without hiding provenance.
5. Accessible by default: keyboard access, semantic structure, visible focus, contrast, and announced status changes.

## Application layout and navigation

Use a persistent left navigation rail on desktop with workspace switcher, Dashboard, Suppliers, Review queue, and Settings. Main content uses a clear page title, breadcrumb when nested, primary action, and contextual filters. On narrow screens, collapse navigation into a labeled menu and preserve core actions without horizontal scrolling. Show current tenant in the application shell.

## Visual tokens

Use a neutral slate foundation, white/near-white surfaces, and restrained indigo or deep blue for primary actions. Status colors supplement text and icons; never rely on color alone. Proposed tokens:

| Token | Initial value | Use |
|---|---|---|
| `color-ink` | `#17212B` | Body text and headings |
| `color-muted` | `#586777` | Supporting text |
| `color-canvas` | `#F5F7FA` | App background |
| `color-surface` | `#FFFFFF` | Cards and tables |
| `color-primary` | `#334E9A` | Primary action and active navigation |
| `color-success` | `#176B52` | Completed/verified state with label |
| `color-warning` | `#8A5200` | Attention/expiring state with label |
| `color-danger` | `#A33434` | Failed/error state with label |
| `radius-control` | `6px` | Inputs and buttons |
| `radius-panel` | `10px` | Cards and dialogs |
| `space-unit` | `4px` | Base spacing scale |

Check actual contrast in implementation before treating these values as final. Typography: system sans-serif stack, 14–16px body, clear 20–28px page headings, tabular numerals for dates/counts. Use consistent 4px spacing increments.

## Core screens

- **Dashboard:** persisted supplier totals, items awaiting review, recent activity, and a focused next-work queue. No invented trend charts or unsupported metrics. Clearly label demo fixtures.
- **Supplier list/detail:** searchable, filterable table with supplier, status, missing documents, last updated; detail view groups profile, documents, findings, and audit history.
- **Document management:** show type, upload date, version, processing status, and safe actions. Upload flow explains accepted types/size and reports validation failures inline.
- **Verification workspace:** split view with document preview and extracted fields/evidence. Findings include rule, severity, confidence/uncertainty, source page/region, and reviewer action. Unknown values stay visibly unknown.
- **Review queue/exception management:** sort by severity/age/supplier, show owner and next action, and distinguish unresolved, in review, and resolved.
- **Review history:** chronological actor/action/reason view; edits create new events rather than erasing decisions.

## Components and interaction states

Use consistent buttons, labeled form fields, status badges with text, tables with sorting labels, pagination, confirmation dialogs for destructive actions, evidence links, document viewer, and accessible toast/inline feedback. Each data area has skeleton/loading, empty with a meaningful next action, recoverable error, permission-denied, and populated states. Upload progress and processing status are distinct. Disable actions only with an explanation.

## Responsive and accessible behavior

At desktop sizes, support a two-pane verification workspace. At tablet/mobile widths, stack the document and findings panes with clear navigation between them. Tables may become labeled cards or scroll within their own region. Preserve keyboard order and focus on dialogs; use `aria-live` for asynchronous upload/processing updates. Provide text alternatives for all status icons and visible focus styling.

## Processing on supplier detail

Each PDF displays its current stage and numbered attempts. Poll queued/processing attempts and expose a safe failure code with a retry action for authorized writers. Successful extraction has a needs-review state. Administrators can inspect raw evidence by page and method. Reviewers see validation statuses and source page locations. The dashboard counts active document versions whose latest extraction needs review. Raw engine confidence, when available, describes OCR recognition only.

## Supplier verification workspace

Administrators configure requirements on the supplier detail page. Each historical run shows its evaluation date and rule/policy versions. The checklist distinguishes received, missing, conditional, unconfirmed and inapplicable requirements. Side-by-side evidence identifies source versions, pages and spans. The administrator can open a cited span; a reviewer sees coordinates and outcomes. The page distinguishes no run, insufficient evidence and conflicts. A review action requires a reason and records an attributed history entry. Dashboard verification_pending counts review-required findings on the latest snapshots of active suppliers, excluding resolved and dismissed findings.

## Exception queue and workspace

Open **Exceptions** from the sidebar or **Open exception** on a supplier finding. Queue counts reflect applied filters. Age measures completed 24-hour periods since finding creation. Minimum age is a user-selected threshold. Older findings appear first within the chosen sort order. Historical and archived-supplier findings stay discoverable.

The detail page shows the original outcome, explanation, recommended action and source locations. Ownership, draft revisions, corrected files, verification comparison and decision history share this page. Role and ownership determine the available controls. The editor previews approved wording and identifies invalid edits. Upload and decision forms require human confirmation. Refresh retrieves current processing and ownership information. History pages show up to 20 records per section.

## Release interface

Shared typography, spacing, contrast, button heights, focus rings and table borders apply across sign-in, supplier management, extraction, verification and exceptions. The shell uses a dark neutral sidebar on desktop and wrapping navigation on smaller screens. Dashboard measurements share a single aligned surface. A keyboard skip link moves focus directly to the workspace. Error messages and statuses include text. The acceptance suite covers the complete workflow at 1280 and 390 CSS pixels and checks tablet overflow and keyboard focus at 768 pixels.
