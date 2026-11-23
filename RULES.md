# Permanent Engineering Rules

This file is authoritative for project engineering. When a change conflicts with a rule, stop and resolve the conflict explicitly in documentation before proceeding.

1. Inspect existing files, branch, commit, and working-tree state before changing code; preserve existing work.
2. No unnecessary rewrites, speculative implementations, premature abstractions, duplicate implementations, or unrelated features.
3. No fake AI capabilities or mock responses presented as production functionality. Label demo mode and illustrative data clearly.
4. No hardcoded credentials, committed secrets, actual supplier/customer documents, local databases, or private uploads.
5. No direct database manipulation outside the defined application architecture; every schema change is represented by a reviewed migration.
6. Do not weaken authentication, authorization, tenant isolation, upload validation, privacy, audit, or other security controls to make a demo work.
7. Do not break API contracts without updating documentation and tests. Do not silently change persisted data semantics.
8. Avoid unnecessary dependency installation; justify each new runtime dependency and pin/lock it through project configuration.
9. Do not claim a change is tested unless the relevant command actually ran successfully. Do not suppress or silently ignore failures.
10. No silent error handling: failures must be visible, safe, attributable, and recoverable where appropriate.
11. Never let AI automatically declare a supplier fraudulent, approve a supplier, authorize payment, or override a human decision.
12. Every important finding must cite evidence or state that evidence is unavailable; preserve uncertainty and provenance.
13. Do not claim unsupported accuracy, customer validation, enterprise adoption, compliance, or business impact.
14. Treat uploaded documents, extracted content, model output, and provider responses as untrusted input.
15. Keep documentation consistent with implemented behavior; mark planned capabilities as planned.
16. Work one roadmap phase at a time. Phase 0 documentation must be completed and reviewed before Phase 1 implementation.
17. Use a disposable PostgreSQL database and synthetic PDFs for integration gates.
18. Never use destructive Git operations or force-push without explicit authorization. Use meaningful commits and verify any push.

19. Keep extraction attempts versioned and immutable after completion. Validate provenance against the captured source segment and run the synthetic evaluation when changing the extractor.

20. Version verification semantics and policy changes. Preserve the complete run basis, explicitly abstain on unsupported evidence, and keep consequential review actions attributed and append-only.
