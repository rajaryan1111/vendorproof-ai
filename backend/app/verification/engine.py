"""Pure verification over one frozen inventory and one policy revision."""

import json
from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations

from pydantic import ValidationError

from ..intelligence.schema import Report
from .normalize import address, calendar_date, company, identifier

VERSION = "verify/1"
ALIASES = {
    "private limited": "private limited",
    "pvt ltd": "private limited",
    "limited": "limited",
    "ltd": "limited",
}
POSITIVE = {"exact_match", "normalized_match", "valid", "received", "not_applicable"}


@dataclass
class Document:
    id: str
    digest: str
    attempt: str | None
    state: str
    report: Report | None

    @classmethod
    def load(cls, row):
        report = None
        if row.report and row.state == "needs_review":
            try:
                candidate = Report.model_validate_json(json.dumps(row.report))
                if (
                    str(candidate.document_id) == str(row.id)
                    and candidate.version_digest == row.digest
                ):
                    report = candidate
            except ValidationError:
                pass
        return cls(
            str(row.id),
            row.digest,
            str(row.attempt) if row.attempt else None,
            row.state or "uploaded",
            report,
        )

    def ref(self):
        return {
            "document": self.id,
            "digest": self.digest,
            "attempt": self.attempt,
            "state": self.state,
        }


def source(doc, key, ref, normalized=None):
    seg = doc.report.pages[ref.page - 1].segments[ref.segment]
    return {
        **doc.ref(),
        "field": key,
        **ref.model_dump(),
        "normalized": normalized,
        "confidence": seg.confidence,
    }


def reliable(ref):
    return ref.get("method") == "native" or (ref.get("confidence") or 0) >= 90


def finding(rule, outcome, why, refs):
    review = outcome not in POSITIVE
    quality = (
        "insufficient"
        if outcome
        in {
            "insufficient",
            "ambiguous",
            "unreadable",
            "unknown_condition",
            "unconfirmed",
            "missing_field",
        }
        else "inventory"
        if rule == "requirement"
        else "sourced"
    )
    severity = (
        "high"
        if outcome == "expired"
        else "medium"
        if outcome in {"conflict", "missing_document"}
        else "low"
        if review
        else "informational"
    )
    return {
        "rule": rule,
        "outcome": outcome,
        "explanation": why,
        "evidence": refs,
        "severity": severity,
        "quality": quality,
        "requires_review": review,
    }


def inspect_document(doc, policy, as_of, groups):
    if not doc.report:
        return "unknown", [
            finding(
                "extraction",
                "insufficient",
                "The received PDF lacks a usable, version-matched extraction.",
                [doc.ref()],
            )
        ]
    report = doc.report
    category = report.classification.category
    headings = [
        source(doc, "classification", r) for r in report.classification.evidence
    ]
    if category == "unknown" or not headings or not all(reliable(r) for r in headings):
        return "unknown", [
            finding(
                "classification",
                "insufficient",
                "The heading does not reliably identify a single document class.",
                headings or [doc.ref()],
            )
        ]
    rules = {r.category: r for r in policy.rules if policy.applies(r) is True}
    rule = rules.get(category)
    scheme = rule.identifier_scheme if rule else None
    aliases = ALIASES if policy.legal_suffix_aliases else {}
    findings = []
    for page in report.pages:
        if page.warning:
            findings.append(
                finding(
                    "page_quality",
                    "insufficient",
                    "Extraction flagged this page: " + page.warning,
                    [{**doc.ref(), "page": page.number}],
                )
            )
    for c in report.candidates:
        if c.status == "conflicting":
            findings.append(
                finding(
                    "within_document",
                    "conflict",
                    "The extraction contains competing values for one field.",
                    [source(doc, c.key, r) for r in c.alternatives],
                )
            )
            continue
        if not c.source:
            continue
        group = None
        if c.key in {"legal_name", "business_name", "account_holder", "policyholder"}:
            group = ("name", "")
            value = company(c.value, aliases)
        elif c.key == "registered_address":
            group = ("address", "")
            value = address(c.value)
        elif c.key in {"registration_number", "tax_id"}:
            group = ("identifier", c.key + ":" + str(scheme))
            value = (
                identifier(c.value, scheme)
                if scheme and (scheme != "uk_company" or c.key == "registration_number")
                else None
            )
        elif c.key == "incorporation_date":
            group = ("incorporation_date", "")
            parsed = calendar_date(c.value)
            value = parsed.isoformat() if parsed else None
        else:
            continue
        ref = source(doc, c.key, c.source, value)
        if not value or not reliable(ref):
            findings.append(
                finding(
                    group[0],
                    "insufficient",
                    "The field lacks a reliable comparable value or a configured identifier namespace.",
                    [ref],
                )
            )
        else:
            groups[group].append(ref)
    findings.extend(validity(doc, rule, as_of, policy.days))
    return category, findings


def validity(doc, rule, today, window):
    if not rule or not (rule.expiry or rule.issue_date):
        return []
    by_key = {c.key: c for c in doc.report.candidates}
    results = []
    for key, on in (("expiry_date", rule.expiry), ("issue_date", rule.issue_date)):
        if not on:
            continue
        c = by_key.get(key)
        if not c or not c.source:
            refs = [source(doc, key, r) for r in c.alternatives] if c else []
            results.append(
                finding(
                    key,
                    "insufficient" if refs else "missing_field",
                    "The configured date has no single supported value.",
                    refs or [doc.ref()],
                )
            )
            continue
        parsed = calendar_date(c.value)
        ref = source(doc, key, c.source, parsed.isoformat() if parsed else None)
        if not reliable(ref):
            outcome = "insufficient"
        elif parsed is None:
            outcome = "ambiguous" if "/" in c.value else "unreadable"
        elif key == "issue_date":
            outcome = "conflict" if parsed > today else "valid"
        elif parsed < today:
            outcome = "expired"
        elif window and (parsed - today).days <= window:
            outcome = "approaching"
        else:
            outcome = "valid"
        results.append(
            finding(
                key,
                outcome,
                f"Evaluated {key.replace('_', ' ')} on {today.isoformat()} UTC with a {window}-day warning window.",
                [ref],
            )
        )
    start = by_key.get("coverage_date") or by_key.get("issue_date")
    end = by_key.get("expiry_date")
    if start and end and start.source and end.source:
        dates = [calendar_date(c.value) for c in (start, end)]
        refs = [
            source(doc, c.key, c.source, d.isoformat() if d else None)
            for c, d in zip((start, end), dates, strict=True)
        ]
        if all(dates) and dates[0] > dates[1]:
            results.append(
                finding(
                    "date_order",
                    "conflict" if all(map(reliable, refs)) else "insufficient",
                    "The start date appears later than the end date.",
                    refs,
                )
            )
    return results


def evaluate(docs, policy, today):
    groups = defaultdict(list)
    results = []
    inventory = []
    for doc in docs:
        category, rows = inspect_document(doc, policy, today, groups)
        inventory.append({**doc.ref(), "category": category})
        results += rows
    for (kind, _namespace), refs in groups.items():
        for left, right in combinations(refs, 2):
            if left["document"] == right["document"]:
                continue
            rule = (
                "bank_holder"
                if kind == "name"
                and "account_holder" in (left["field"], right["field"])
                else kind
            )
            if left["original"] == right["original"]:
                outcome = "exact_match"
            elif left["normalized"] == right["normalized"]:
                outcome = "normalized_match"
            elif "ocr" in (left["method"], right["method"]):
                outcome = "insufficient"
            else:
                outcome = "conflict"
            explanation = {
                "exact_match": "The two cited values are identical.",
                "normalized_match": "The cited values agree under the configured formatting rules.",
                "insufficient": "An OCR-derived difference needs inspection before comparison.",
                "conflict": "The two cited values differ after normalization. Inspect both originals.",
            }[outcome]
            results.append(finding(rule, outcome, explanation, [left, right]))
    if not any(len({r["document"] for r in refs}) >= 2 for refs in groups.values()):
        results.append(
            finding(
                "comparison",
                "insufficient",
                "No pair of documents supplies reliable values of the same comparable type.",
                inventory,
            )
        )
    checklist = []
    for rule in policy.rules:
        applicable = policy.applies(rule)
        received = [d for d in inventory if d["category"] == rule.category]
        unknown = [d for d in inventory if d["category"] == "unknown"]
        state = (
            "not_applicable"
            if applicable is False
            else "unknown_condition"
            if applicable is None
            else "received"
            if received
            else "unconfirmed"
            if unknown
            else "missing_document"
        )
        checklist.append(
            {
                "category": rule.category,
                "outcome": state,
                "received": [d["document"] for d in received],
                "when_type": rule.when_type,
                "when_jurisdiction": rule.when_jurisdiction,
                "expiry_check": rule.expiry and applicable is True,
            }
        )
        results.append(
            finding(
                "requirement",
                state,
                f"{rule.category}: {state.replace('_', ' ')} under the recorded supplier policy.",
                received or inventory,
            )
        )
    return inventory, checklist, results
