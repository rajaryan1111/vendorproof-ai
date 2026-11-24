"""Resolution guidance uses only controlled rule metadata."""

from fastapi import HTTPException

TERMINAL = {"resolved", "dismissed"}
MOVES = {
    "open": {
        "in_progress",
        "awaiting_internal_review",
        "awaiting_supplier_response",
        "resolved",
        "dismissed",
    },
    "assigned": {
        "in_progress",
        "awaiting_internal_review",
        "awaiting_supplier_response",
        "resolved",
        "dismissed",
    },
    "in_progress": {
        "awaiting_internal_review",
        "awaiting_supplier_response",
        "resolved",
        "dismissed",
    },
    "awaiting_supplier_response": {
        "in_progress",
        "awaiting_internal_review",
        "dismissed",
    },
    "awaiting_internal_review": {
        "in_progress",
        "awaiting_supplier_response",
        "resolved",
        "dismissed",
    },
    "resolved": {"reopened"},
    "dismissed": {"reopened"},
    "reopened": {
        "in_progress",
        "awaiting_internal_review",
        "awaiting_supplier_response",
        "resolved",
        "dismissed",
    },
}


def owner_write(user, item):
    if user.role != "admin" and (
        user.role != "reviewer" or item.assignee != user.actor
    ):
        raise HTTPException(403)


def guidance(rule, outcome, explanation):
    categories = {"registration", "tax", "bank", "insurance", "agreement"}
    category = explanation.partition(":")[0]
    if (
        rule == "requirement"
        and outcome == "missing_document"
        and category in categories
    ):
        action = f"Please provide the required {category} document."
    elif rule == "expiry_date" and outcome == "expired":
        action = "Please provide a current document showing the validity period."
    elif outcome in {
        "insufficient",
        "ambiguous",
        "unconfirmed",
        "unreadable",
        "unknown_condition",
        "missing_field",
    }:
        action = "Please clarify the applicable requirement or provide a clearer supporting document."
    elif rule == "bank_holder":
        action = "Please clarify the account holder name and provide supporting documentation."
    elif rule in {"name", "identifier", "address", "within_document"}:
        action = "Please clarify the differing registration details and provide supporting documentation."
    else:
        action = "Please clarify the recorded document details and provide current supporting evidence."
    subjects = [
        "Request for supporting documentation",
        "Clarification of supplier documentation",
    ]
    if outcome == "missing_document":
        context = "Our document checklist requires additional documentation."
    elif outcome == "expired":
        context = "The validity period shown in the supplied document has ended."
    elif outcome == "conflict":
        context = (
            "The supplied records contain differing details that require clarification."
        )
    else:
        context = "The available documentation provides insufficient evidence to complete this check."
    sentences = [
        context,
        action,
        "A clearer copy would assist our review.",
        "Please identify the document being replaced.",
        "Thank you for your assistance.",
    ]
    return {
        "rule": rule,
        "outcome": outcome,
        "why": explanation,
        "action": action,
        "subjects": subjects,
        "sentences": sentences,
        "subject": subjects[0],
        "message": context + "\n" + action,
    }


def validate_draft(body, guide):
    lines = body.message.splitlines()
    if (
        body.subject not in guide["subjects"]
        or not lines
        or len(lines) > 5
        or len(set(lines)) != len(lines)
        or guide["action"] not in lines
        or any(line not in guide["sentences"] for line in lines)
    ):
        raise HTTPException(422)
