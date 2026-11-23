import re
from typing import Protocol

from .schema import TITLES, Candidate, Classification, Report, Source, fields, normalize


def matches(pages, pattern):
    for page in pages:
        for i, seg in enumerate(page.segments):
            for match in re.finditer(pattern, seg.text, re.IGNORECASE | re.MULTILINE):
                yield Source(
                    page=page.number,
                    segment=i,
                    start=match.start(1),
                    end=match.end(1),
                    method=seg.method,
                    original=match[1],
                )


def alternatives(labels):
    return "|".join(map(re.escape, labels))


def classify(pages):
    hits = {
        category: list(matches(pages, r"^[ \t]*(" + alternatives(labels) + r")[ \t]*$"))
        for category, labels in TITLES.items()
    }
    found = [key for key, value in hits.items() if value]
    return Classification(
        category=found[0] if len(found) == 1 else "unknown",
        status="suggested"
        if len(found) == 1
        else "ambiguous"
        if found
        else "unsupported",
        evidence=[src for values in hits.values() for src in values],
    )


class Provider(Protocol):
    def extract(self, pages, category) -> list[Candidate]: ...


class OfflineProvider:
    def extract(self, pages, category):
        candidates = []
        for key, labels in fields(category).items():
            pattern = (
                r"^[ \t]*(?:"
                + alternatives(labels)
                + r")[ \t]*:[ \t]*([^\n\r]{0,511}?\S)[ \t]*$"
            )
            hits = list(matches(pages, pattern))
            distinct = {ref.original.strip() for ref in hits}
            ref = hits[0] if len(distinct) == 1 else None
            value = ref.original if ref else None
            normalized = normalize(key, value) if value else None
            status = (
                ("candidate" if normalized else "invalid_date")
                if ref
                else ("conflicting" if hits else "missing")
            )
            candidates.append(
                Candidate(
                    key=key,
                    value=value,
                    normalized=normalized,
                    source=ref,
                    alternatives=hits if status == "conflicting" else [],
                    status=status,
                )
            )
        return candidates


def build_report(key, digest, pages, provider: Provider | None = None):
    classification = classify(pages)
    candidates = (provider or OfflineProvider()).extract(pages, classification.category)
    return Report(
        document_id=key,
        version_digest=digest,
        pages=pages,
        classification=classification,
        candidates=candidates,
    )
