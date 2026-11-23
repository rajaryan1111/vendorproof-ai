"""Run from backend: python -m evaluation.v1.measure"""

import hashlib
import json
import statistics
import time
import tracemalloc
from collections import Counter, defaultdict
from pathlib import Path
from uuid import UUID

from app.intelligence.extract import build_report
from app.intelligence.pages import ProcessingError, read_pages

from .fixtures import make_pdf


def distance(a, b):
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        curr = [i]
        for j, y in enumerate(b, 1):
            curr.append(min(curr[-1] + 1, prev[j] + 1, prev[j - 1] + (x != y)))
        prev = curr
    return prev[-1]


def rate(n, d):
    return round(n / d, 4) if d else None


def evaluate():
    cases = json.loads(Path(__file__).with_name("corpus.json").read_text())
    slots = json.loads(Path(__file__).with_name("slots.json").read_text())
    matrix = defaultdict(Counter)
    measures = Counter()
    by_field = defaultdict(Counter)
    times = []
    tracemalloc.start()
    for i, case in enumerate(cases, 1):
        pdf = make_pdf(case)
        started = time.perf_counter()
        try:
            pages = read_pages(pdf, "eng")
            report = build_report(UUID(int=i), hashlib.sha256(pdf).hexdigest(), pages)
        except (ValueError, ProcessingError) as exc:
            measures["failures"] += 1
            measures["invalid_outputs"] += isinstance(exc, ValueError)
            continue
        finally:
            times.append(time.perf_counter() - started)
        matrix[case["category"]][report.classification.category] += 1
        for page, expected, medium in zip(
            pages, case["pages"], case["media"], strict=True
        ):
            observed = " ".join(s.text for s in page.segments)
            measures["readable_truth"] += bool(expected)
            measures["readable_recovered"] += bool(expected and observed)
            measures["empty_correct"] += bool(expected) == bool(observed)
            measures["pages"] += 1
            measures["empty_truth"] += not expected
            if medium in {"scan", "degraded"}:
                a, b = " ".join(expected.split()), " ".join(observed.split())
                measures["ocr_pages"] += 1
                measures["ocr_read"] += bool(observed)
                measures["char_errors"] += distance(a, b)
                measures["chars"] += len(a)
                measures["word_errors"] += distance(a.split(), b.split())
                measures["words"] += len(a.split())
        predictions = {c.key: c for c in report.candidates}
        for key in slots[case["category"]]:
            truth = case["values"].get(key)
            cand = predictions.get(key)
            value = cand.value if cand else None
            measures["slots"] += 1
            measures["abstentions"] += value is None
            missing = truth is None and key not in case.get("conflicts", [])
            predicted_missing = bool(cand and cand.status == "missing")
            measures["missing_truth"] += missing
            measures["missing_predictions"] += predicted_missing
            measures["missing_correct"] += predicted_missing and missing
            if truth is not None:
                measures["positive"] += 1
                by_field[key]["n"] += 1
                by_field[key]["exact"] += value == truth
                by_field[key]["normalized"] += bool(
                    value and " ".join(value.split()) == " ".join(truth.split())
                )
                if cand and cand.source:
                    ref = cand.source
                    expected_page = case["pages"][ref.page - 1]
                    measures["localized"] += bool(
                        truth in expected_page
                        and ref.original == truth
                        and pages[ref.page - 1]
                        .segments[ref.segment]
                        .text[ref.start : ref.end]
                        == truth
                    )
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    labels = list(slots)
    exact = sum(v["exact"] for v in by_field.values())
    normal = sum(v["normalized"] for v in by_field.values())
    return {
        "dataset": "synthetic-v1",
        "documents": len(cases),
        "counts": dict(measures),
        "page_success": rate(
            measures["readable_recovered"], measures["readable_truth"]
        ),
        "empty_detection_accuracy": rate(measures["empty_correct"], measures["pages"]),
        "failure_rate": rate(measures["failures"], len(cases)),
        "CER": rate(measures["char_errors"], measures["chars"]),
        "WER": rate(measures["word_errors"], measures["words"]),
        "ocr_page_success": rate(measures["ocr_read"], measures["ocr_pages"]),
        "classification": {
            k: {
                "precision": rate(matrix[k][k], sum(matrix[t][k] for t in labels)),
                "recall": rate(matrix[k][k], sum(matrix[k].values())),
            }
            for k in labels
        },
        "confusion_truth_rows": {k: {t: matrix[k][t] for t in labels} for k in labels},
        "positive_field_exact": rate(exact, measures["positive"]),
        "positive_field_normalized": rate(normal, measures["positive"]),
        "per_field": dict(by_field),
        "missing_precision": rate(
            measures["missing_correct"], measures["missing_predictions"]
        ),
        "missing_recall": rate(measures["missing_correct"], measures["missing_truth"]),
        "evidence_localization": rate(measures["localized"], measures["positive"]),
        "abstention": rate(measures["abstentions"], measures["slots"]),
        "invalid_output_rate": rate(measures["invalid_outputs"], len(cases)),
        "median_seconds": round(statistics.median(times), 3),
        "max_seconds": round(max(times), 3),
        "peak_python_allocated_bytes": peak,
        "provider_tokens": 0,
        "external_calls": 0,
    }


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))
