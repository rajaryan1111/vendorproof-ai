"""Run from backend: python -m evaluation.verification_v1.measure"""

import hashlib
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from statistics import median
from time import perf_counter
from types import SimpleNamespace
from uuid import UUID

from app.intelligence.extract import build_report
from app.intelligence.schema import Page, Segment
from app.verification.engine import VERSION, Document, evaluate
from app.verification.policy import Policy

CASES = json.loads(Path(__file__).with_name("cases.json").read_text())
ALERT = {
    "expired",
    "approaching",
    "missing_document",
    "conflict",
    "insufficient",
    "unconfirmed",
    "unknown_condition",
    "missing_field",
    "ambiguous",
    "unreadable",
}
ABSTAIN = {
    "insufficient",
    "unconfirmed",
    "unknown_condition",
    "ambiguous",
    "unreadable",
    "missing_field",
}


def inputs(case):
    docs = []
    for i, text in enumerate(case["docs"]):
        key = UUID(int=i + 1)
        digest = hashlib.sha256(text.encode()).hexdigest()
        if text == "FAILED":
            docs.append(Document(str(key), digest, None, "failed", None))
            continue
        ocr = i == case.get("ocr")
        seg = Segment(
            method="ocr" if ocr else "native",
            text=text,
            confidence=95.0 if ocr else None,
        )
        page = Page(
            number=1,
            segments=[seg],
            characters=len(text),
            words=len(text.split()),
            warning="sparse_text" if case.get("warning") else None,
        )
        report = build_report(key, digest, [page]).model_dump(mode="json")
        if case.get("tamper"):
            next(c for c in report["candidates"] if c["source"])["source"]["end"] += 1
        docs.append(
            Document.load(
                SimpleNamespace(
                    id=key,
                    digest=digest,
                    attempt=UUID(int=i + 101),
                    state="needs_review",
                    report=report,
                )
            )
        )
    policy = Policy(
        legal_suffix_aliases=True,
        supplier_type=case.get("type"),
        rules=case.get("rules", []),
    )
    return docs, policy


def score():
    counters = defaultdict(Counter)
    errors = []
    times = []
    anchors = anchored = abstentions = work = 0
    for case in CASES:
        docs, policy = inputs(case)
        t = perf_counter()
        _, _, results = evaluate(docs, policy, date(2026, 11, 24))
        times.append((perf_counter() - t) * 1000)
        rows = [r for r in results if r["rule"] == case["rule"]]
        outcomes = [r["outcome"] for r in rows] or ["none"]
        if outcomes != [case["outcome"]]:
            errors.append(case["id"])
        wanted = case["outcome"] in ALERT
        actual = any(o in ALERT for o in outcomes)
        counts = counters[case["rule"]]
        counts[
            "tp" if wanted and actual else "fn" if wanted else "fp" if actual else "tn"
        ] += 1
        abstentions += any(o in ABSTAIN for o in outcomes)
        work += sum(r["requires_review"] for r in results)
        refs = [r for f in rows for r in f["evidence"] if "original" in r]
        for v, expected_doc in zip(
            case.get("values", []), case.get("source_documents", []), strict=True
        ):
            anchors += 1
            for ref in refs:
                idx = int(UUID(ref["document"])) - 1
                text = case["docs"][idx]
                if (
                    idx + 1 == expected_doc
                    and ref["digest"] == hashlib.sha256(text.encode()).hexdigest()
                    and ref["attempt"] == str(UUID(int=idx + 101))
                    and ref["page"] == 1
                    and ref["segment"] == 0
                    and ref["original"] == v
                    and text[ref["start"] : ref["end"]] == v
                ):
                    anchored += 1
                    refs.remove(ref)
                    break

    def ratio(n, d):
        return round(n / d, 4) if d else None

    totals = sum(counters.values(), Counter())

    def rates(c):
        return {
            "tp": c["tp"],
            "fp": c["fp"],
            "tn": c["tn"],
            "fn": c["fn"],
            "precision": ratio(c["tp"], c["tp"] + c["fp"]),
            "recall": ratio(c["tp"], c["tp"] + c["fn"]),
        }

    return {
        "rule_version": VERSION,
        "cases": len(CASES),
        "target_outcome_errors": errors,
        "per_rule": {k: rates(c) for k, c in counters.items()},
        "total": rates(totals),
        "fpr": ratio(totals["fp"], totals["fp"] + totals["tn"]),
        "fnr": ratio(totals["fn"], totals["fn"] + totals["tp"]),
        "abstaining_target_cases": abstentions,
        "abstention_rate": ratio(abstentions, len(CASES)),
        "localized_value_references": [anchored, anchors],
        "review_findings_all_rules": work,
        "median_engine_ms": round(median(times), 4),
        "max_engine_ms": round(max(times), 4),
    }


if __name__ == "__main__":
    print(json.dumps(score(), indent=2))
