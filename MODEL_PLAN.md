# VendorProof AI Model and Document Intelligence Plan

**Status:** Planned for Phase 2 onward. Phase 0 and Phase 1 contain no AI extraction capability.

Phase 1 labels a validated PDF as stored. This status records successful intake only.

## Processing pipeline

1. Validate upload and create an immutable document version.
2. Detect supported format and extract text/layout. Use PyMuPDF for text PDFs; use Tesseract OCR for scanned pages in the initial local implementation, with Pillow preprocessing only if evaluation shows value.
3. Classify document type with deterministic metadata/rules first; measure errors before adding model classification.
4. Extract only approved fields into strict Pydantic schemas; retain page and bounding-region or text-span provenance, raw candidate, normalized candidate, and confidence/uncertainty.
5. Validate types, dates, required values, and allowed formats deterministically. Invalid values become unresolved candidates, not guessed values.
6. Compare normalized fields and configured requirements with deterministic rules. Produce findings linked to document version, source evidence, and rule version.
7. Request human review when evidence is missing, conflicting, low quality, or ambiguous.

## AI requirements

- **AI-001 Provenance:** every extracted candidate retains a document-version and page/region or text-span reference; otherwise it is marked unsupported and withheld from findings.
- **AI-002 Deterministic checks:** normalization, required-document checks, expiry, and comparisons use versioned deterministic rules wherever reliable.
- **AI-003 Human authority:** model output never determines fraud, supplier approval, or payment authorization; uncertain or consequential results require an authorized person.
- **AI-004 Bounded provider use:** provider output is schema-validated and checked deterministically; requests are minimized, bounded, and optional so offline mode remains explicit.
- **AI-005 Measured quality:** extraction and comparison changes are evaluated against labeled test data, with limitations, sample sizes, latency, and cost recorded before claims or rollout.

## Schemas and provenance

Define versioned Pydantic models per document class and a common extracted-field record: field key, candidate value, normalized value, source reference, extraction method/model version, confidence where calibrated, and review state. A source reference identifies document version, page, and text span or bounding box. Do not expose chain-of-thought; record concise rationale grounded in evidence if needed.

## Normalization and comparison

Use deterministic normalization for whitespace/case, known legal suffixes, address components, country-specific registration formats, currencies, and dates only where jurisdiction rules are configured. Preserve original values alongside normalized forms. Never merge two records or assert identity based on a fuzzy score alone. Comparison rules distinguish exact match, normalized match, conflict, missing, expired, and insufficient evidence. Thresholds and rule versions are explicit and testable.

## LLM boundary and controls

LLMs are optional and limited to bounded extraction or ambiguity assistance when deterministic methods are inadequate. Require structured output validated against a schema, provider abstraction, explicit timeout/token limits, redacted/minimized inputs where possible, and deterministic post-validation. The model cannot determine fraud, make approval decisions, invent evidence, or override rule results. Missing evidence yields unknown/needs review. Provider access is configurable; offline tests use a deterministic mock provider and do not imply production capability.

## Evaluation

Create a synthetic, versioned evaluation corpus and, only with governance approval, a separately controlled representative corpus. Annotate field values, evidence spans, document class, and ambiguity. Measure field-level exact/normalized accuracy, precision/recall for conflicts/expiry/missingness, evidence localization accuracy, abstention/uncertainty calibration, failure rate, latency, and estimated token/provider cost. Report per-field and per-document-class results with sample size and limitations; do not make unsupported accuracy claims. Add regression cases for OCR noise, contradictory documents, aliases, date formats, blank fields, and prompt injection embedded in documents.

## Safety, operations, and cost

Treat document text as untrusted data, never as instructions. Keep extraction versions and rule versions so results can be reproduced. Track processing state and bounded errors without logging document contents. Establish latency/cost budgets using measured workload before selecting a provider. Keep provider adapters replaceable; do not add RAG, embeddings, vector databases, fine-tuning, or multi-agent orchestration absent a demonstrated requirement.
