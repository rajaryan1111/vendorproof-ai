"""Versioned, offline report contract. Offsets count Python Unicode code points."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA = "fields/1"
ENGINE = "local/1"
Category = Literal["registration", "tax", "bank", "insurance", "agreement", "unknown"]
TITLES = {
    "registration": (
        "company registration certificate",
        "certificate of incorporation",
    ),
    "tax": ("tax registration document", "tax registration certificate"),
    "bank": ("bank verification document", "bank verification letter"),
    "insurance": ("insurance certificate", "certificate of insurance"),
    "agreement": ("supplier agreement", "supply agreement"),
}
COMMON = {
    "legal_name": ("legal company name", "legal name", "company name"),
    "trading_name": ("trading name",),
    "registered_address": ("registered address", "registered office"),
    "registration_number": ("registration number", "registration identifier"),
    "document_date": ("document date",),
    "issuing_authority": ("issuing authority",),
}
FIELDS = {
    "registration": {"incorporation_date": ("incorporation date",)},
    "tax": {
        "tax_id": ("tax registration identifier", "tax id"),
        "business_name": ("registered business name",),
        "issue_date": ("issue date",),
        "expiry_date": ("expiry date", "valid until"),
    },
    "bank": {
        "account_holder": ("account holder name", "account holder"),
        "bank_name": ("bank name",),
        "ifsc": ("ifsc",),
    },
    "insurance": {
        "policyholder": ("policyholder",),
        "policy_number": ("policy number",),
        "coverage_date": ("coverage start", "coverage date"),
        "expiry_date": ("expiry date", "coverage end"),
        "insurer": ("insurer",),
    },
    "agreement": {
        "parties": ("parties",),
        "agreement_date": ("agreement date",),
        "expiry_date": ("expiry date",),
        "signature_evidence": ("signature evidence",),
    },
    "unknown": {},
}


def fields(category):
    return {} if category == "unknown" else COMMON | FIELDS[category]


def normalize(key, value):
    value = " ".join(value.split())
    if key.endswith("_date"):
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError:
            return None
    return value


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Segment(Strict):
    method: Literal["native", "ocr"]
    text: str = Field(max_length=100000)
    bbox: tuple[float, float, float, float] | None = None
    confidence: float | None = Field(None, ge=0, le=100)


class Page(Strict):
    number: int = Field(ge=1)
    segments: list[Segment]
    characters: int
    words: int
    warning: str | None = None


class Source(Strict):
    page: int = Field(ge=1)
    segment: int = Field(ge=0)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    method: Literal["native", "ocr"]
    original: str = Field(min_length=1, max_length=512)


class Candidate(Strict):
    key: str
    value: str | None
    normalized: str | None
    alternatives: list[Source] = Field(default_factory=list)
    source: Source | None
    status: Literal["candidate", "missing", "conflicting", "invalid_date"]


class Classification(Strict):
    category: Category
    status: Literal["suggested", "ambiguous", "unsupported"]
    method: Literal["title_match"] = "title_match"
    evidence: list[Source]


class Report(Strict):
    document_id: UUID
    version_digest: str = Field(pattern="^[a-f0-9]{64}$")
    schema_version: Literal["fields/1"] = SCHEMA
    implementation: Literal["local/1"] = ENGINE
    review_status: Literal["needs_review"] = "needs_review"
    pages: list[Page]
    classification: Classification
    candidates: list[Candidate]

    @model_validator(mode="after")
    def validate_sources(self):
        if [p.number for p in self.pages] != list(
            range(1, len(self.pages) + 1)
        ) or not self.pages:
            raise ValueError("invalid page sequence")
        classification = self.classification
        signals = {
            cat
            for ref in classification.evidence
            for cat, labels in TITLES.items()
            if ref.original.lower() in labels
        }
        if len(signals) == 1:
            valid = (
                classification.category in signals
                and classification.status == "suggested"
            )
        else:
            valid = classification.category == "unknown" and classification.status == (
                "ambiguous" if signals else "unsupported"
            )
        if not valid:
            raise ValueError("unsupported classification")
        expected = fields(classification.category)
        if sorted(expected) != sorted(c.key for c in self.candidates):
            raise ValueError("incorrect fields for category")
        evidence = list(self.classification.evidence)
        for c in self.candidates:
            if (c.status == "conflicting") != bool(c.alternatives) or (
                c.alternatives and len({r.original for r in c.alternatives}) < 2
            ):
                raise ValueError("conflict needs competing evidence")
            evidence.extend(c.alternatives)
            if c.status in {"missing", "conflicting"}:
                if any(v is not None for v in (c.value, c.source, c.normalized)):
                    raise ValueError("unsupported value")
                continue
            if (
                not c.source
                or c.value != c.source.original
                or c.normalized != normalize(c.key, c.value)
                or (c.normalized is None) != (c.status == "invalid_date")
            ):
                raise ValueError("inconsistent candidate")
            evidence.append(c.source)
        for ref in evidence:
            if (
                ref.page > len(self.pages)
                or self.pages[ref.page - 1].number != ref.page
                or ref.segment >= len(self.pages[ref.page - 1].segments)
            ):
                raise ValueError("missing source")
            segment = self.pages[ref.page - 1].segments[ref.segment]
            if (
                ref.method != segment.method
                or not ref.start < ref.end <= len(segment.text)
                or segment.text[ref.start : ref.end] != ref.original
            ):
                raise ValueError("unsupported evidence")
        for c in self.candidates:
            for ref in ([c.source] if c.source else []) + c.alternatives:
                text = self.pages[ref.page - 1].segments[ref.segment].text
                label = text[: ref.start].split("\n")[-1].strip()
                if (
                    not label.endswith(":")
                    or label[:-1].strip().lower() not in expected[c.key]
                ):
                    raise ValueError("unsupported field attribution")
        return self
