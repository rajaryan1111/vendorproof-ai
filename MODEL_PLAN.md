# VendorProof AI Model and Document Intelligence Plan

**Status:** Phase 2 ships a deterministic offline extractor. Phase 3 consumes its validated outputs using the deterministic verify/1 rules.

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

## Implemented report and evaluation

PyMuPDF reads each page in reading order. Tesseract processes sparse or garbled pages and up to four substantial image regions on mixed pages. OCR retains line confidence (the arithmetic mean of the Tesseract word scores) and bounding rectangles in rendered-page points. Each candidate cites a page, segment and half-open Unicode character range. The format does not reconstruct arbitrary tables or infer a handwritten signature. Signature evidence means a labeled textual statement only.

Version fields/1 defines common and class-specific keys. A single recognized heading suggests the class. Absent or competing headings yield unknown. Labeled values remain candidates, competing values retain separate evidence, and invalid dates retain the original with null normalization. Account numbers are omitted from the field catalog. Page evidence can still contain them. The offline provider interface has no network implementation, API keys or token charges. A bounded child process validates schema and provenance before publication.

The synthetic-v1 corpus holds reference page transcripts, rendering instructions and expected values, with an independent slot manifest. The evaluation generates PDF bytes in memory. CER and WER use edit distance on whitespace-collapsed scanned-page transcripts. Field exact and whitespace-normalized matches use the 17 labeled values as denominator. Localization requires the reference page, exact value and matching source slice. Missing-value precision/recall treat conflicts as a separate state. Abstention counts null predictions across all expected slots. The confusion matrix uses truth rows and predicted columns. Runtime measures local parser and extraction calls, excluding PDF generation, worker startup, database and UI. Peak memory counts Python allocations only; native parser and OCR process RSS are excluded.

See backend/evaluation/v1/results.json for per-field counts, all six classification rows and denominators. The corpus uses few synthetic templates in English, with a single degraded scan. These measurements exercise the implementation and cannot establish production accuracy.

## Verification inputs and limits

verify/1 revalidates the fields/1 report, document UUID, SHA-256 and source offsets before evaluation. Name comparison covers legal/business names, policyholders and bank account holders. Case, spaces and selected punctuation normalize deterministically. Explicit policy enables the Ltd/Limited and Pvt Ltd/Private Limited aliases. Other legal forms remain distinct. Address normalization retains unit numbers and ranges and expands recognized street suffixes. Exact local identifiers retain formatting. UK company numbers remove spaces and normalize case within their configured namespace. Tax and registration keys never share a comparison group.

Unambiguous ISO dates, English day-month-name dates and slash dates with one valid interpretation use calendar dates. Expiry is inclusive through the stated date in UTC. A positive warning window includes the last day and the configured threshold. Zero disables approaching-expiry alerts. Registration expiry requires a jurisdiction-specific policy; its current extraction schema may lack an expiry candidate. Distinct incorporation dates, future issue dates and starts after expiry can raise review findings.

Unsupported source data, failed processing and uncertain classifications produce abstentions. An OCR score below 90 cannot establish a comparable candidate, and a cross-document difference involving OCR requires source inspection. This threshold is an engineering heuristic. Severity is a triage label. No verification rule uses a model or a probability of fraud.

## Correction guidance

Guidance is a local deterministic mapping from the historical rule, outcome and recognized requirement category. Users see the original rule explanation alongside the requested action. An expired date, a missing agreement and a name discrepancy produce different instructions. Insufficient extraction requests clarification or a clearer copy. Draft wording draws only from controlled sentences and subjects. This stage performs no inference on supplier text and makes no provider calls.
