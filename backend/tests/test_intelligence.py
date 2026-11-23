import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.intelligence.extract import OfflineProvider, build_report
from app.intelligence.pages import ProcessingError, read_pages
from app.intelligence.schema import Report, Segment
from evaluation.v1.fixtures import make_pdf

CASES = json.loads(
    (Path(__file__).resolve().parents[1] / "evaluation/v1/corpus.json").read_text()
)


def report(case, provider=None):
    data = make_pdf(case)
    return build_report(
        uuid4(), hashlib.sha256(data).hexdigest(), read_pages(data, "eng"), provider
    )


@pytest.mark.parametrize("index", [0, 1, 2, 3, 4, 5, 6, 7, 8, 10])
def test_corpus(index):
    case = CASES[index]
    result = report(case)
    assert result.classification.category == case["category"]
    assert result.review_status == "needs_review"
    by_key = {c.key: c for c in result.candidates}
    for key, value in case["values"].items():
        assert by_key[key].value.split() == value.split()
    if index == 1:
        seg = result.pages[0].segments[0]
        assert seg.method == "ocr" and seg.bbox and seg.confidence is not None
    if index == 4:
        assert result.pages[1].warning == "unreadable_page"
    if index == 5:
        assert by_key["legal_name"].status == "conflicting"
        assert len(by_key["legal_name"].alternatives) == 2
    if index == 6:
        assert by_key["expiry_date"].status == "invalid_date"
        assert by_key["expiry_date"].normalized is None
    if index == 8:
        assert result.classification.status == "ambiguous"
    if index == 10:
        assert result.pages[0].warning == "mixed_page_native_only"
    assert Report.model_validate_json(result.model_dump_json()) == result


def test_reject_fabricated_evidence():
    class MockProvider(OfflineProvider):
        def extract(self, pages, category):
            result = super().extract(pages, category)
            result[0].value = "Unsupported"
            return result

    with pytest.raises(ValidationError):
        report(CASES[0], MockProvider())
    with pytest.raises(ValidationError):
        Segment(method="ocr", text="x", confidence=101)


def test_provider_error():
    class FailingProvider:
        def extract(self, pages, category):
            raise TimeoutError

    with pytest.raises(TimeoutError):
        report(CASES[0], FailingProvider())


def test_parser_and_ocr_errors(monkeypatch):
    with pytest.raises(ProcessingError, match="pdf_read_failed"):
        read_pages(b"broken", "eng")
    monkeypatch.setenv("PATH", "/nonexistent")
    with pytest.raises(ProcessingError, match="ocr_unavailable"):
        read_pages(make_pdf(CASES[1]), "eng")
