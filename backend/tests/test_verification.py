from datetime import date

import pytest

from app.verification.engine import evaluate
from app.verification.normalize import address, calendar_date, company
from evaluation.verification_v1.measure import CASES, inputs, score


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_expected_decision(case):
    docs, policy = inputs(case)
    _, _, rows = evaluate(docs, policy, date(2026, 11, 24))
    assert ([r["outcome"] for r in rows if r["rule"] == case["rule"]] or ["none"]) == [
        case["outcome"]
    ]


def test_evidence_grounding():
    found, expected = score()["localized_value_references"]
    assert expected > 0 and found == expected


def test_normalization_boundaries():
    assert calendar_date("02/03/2025") is None
    assert calendar_date("25/03/2025") == date(2025, 3, 25)
    assert calendar_date("02/29/2025") is None
    assert company("Oak Ltd", {}) != company("Oak LLC", {})
    assert address("10-12 Oak Rd") != address("1012 Oak Road")


def test_invalid_dates_and_sensitive_serialization():
    from app.verification.api import safe
    from app.verification.normalize import ambiguous_date

    assert not ambiguous_date("31/31/2024")
    assert ambiguous_date("01/03/2024")
    assert calendar_date("03/03/2024") == date(2024, 3, 3)
    assert safe("1234 5678 9012") == "[restricted]"


def test_expiry_policy_boundaries():
    from pydantic import ValidationError

    from app.verification.policy import Policy

    with pytest.raises(ValidationError):
        Policy(rules=[{"category": "registration", "expiry": True}])
    docs, policy = inputs(next(c for c in CASES if c["id"] == "expires_today"))
    policy.days = 0
    assert (
        next(
            f
            for f in evaluate(docs, policy, date(2026, 11, 24))[2]
            if f["rule"] == "expiry_date"
        )["outcome"]
        == "valid"
    )
    policy.days = 30
    assert (
        next(
            f
            for f in evaluate(docs, policy, date(2026, 10, 25))[2]
            if f["rule"] == "expiry_date"
        )["outcome"]
        == "approaching"
    )
