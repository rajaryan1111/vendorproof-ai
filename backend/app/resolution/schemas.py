"""Public exception responses contain only explicitly approved fields."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class Item(BaseModel):
    id: UUID
    supplier_id: UUID
    supplier: str
    archived: bool
    run_id: UUID
    rule: str
    outcome: str
    severity: str
    created_at: datetime
    status: str
    assignee: UUID | None
    owner: str | None
    revision: int


class Counts(BaseModel):
    total: int
    mine: int
    unassigned: int


class Queue(BaseModel):
    items: list[Item]
    counts: Counts
    page: int


class Member(BaseModel):
    id: UUID
    email: str


class Evidence(BaseModel):
    document: UUID
    digest: str
    attempt: UUID | None = None
    state: str | None = None
    field: str | None = None
    page: int | None = None
    segment: int | None = None
    method: str | None = None


class Guidance(BaseModel):
    rule: str
    outcome: str
    why: str
    action: str
    subjects: list[str]
    sentences: list[str]
    subject: str
    message: str


class Review(BaseModel):
    seq: int
    actor: UUID
    actor_name: str
    created_at: datetime
    kind: str
    from_state: str | None
    status: str
    reason: str | None = None
    assignee: UUID | None
    assigned_to: str | None
    compared_run: UUID | None
    correction_doc: UUID | None


class DraftRevision(BaseModel):
    revision: int


class SavedDraft(DraftRevision):
    subject: str
    message: str
    actor: UUID
    created_at: datetime


class Correction(BaseModel):
    document_id: UUID
    actor: UUID
    created_at: datetime
    digest: str
    replaces: UUID | None
    archived: bool
    state: str
    attempt: UUID
    error_code: str | None


class ComparedFinding(BaseModel):
    id: UUID
    outcome: str
    evidence: list[Evidence]
    requires_review: bool


class Comparison(BaseModel):
    compared_run: UUID
    correction_doc: UUID
    current: list[ComparedFinding]


class Detail(Item):
    guidance: Guidance
    evidence: list[Evidence]
    history: list[Review]
    drafts: list[SavedDraft]
    corrections: list[Correction]
    replacement_targets: list[UUID]
    comparison: Comparison | None
    transitions: list[str]
    can_edit: bool
    page: int


class Event(BaseModel):
    seq: int
    status: str
