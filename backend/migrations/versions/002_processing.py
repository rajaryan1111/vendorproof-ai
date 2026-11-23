from alembic import op

revision = "002_processing"
down_revision = "001_workspace"


def upgrade():
    op.execute("""CREATE TABLE processing_attempts(
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), organization_id uuid NOT NULL, supplier_id uuid NOT NULL, document_id uuid NOT NULL,
    attempt integer NOT NULL CHECK(attempt BETWEEN 1 AND 10), implementation text NOT NULL, schema_version text NOT NULL,
    state text NOT NULL DEFAULT 'queued' CHECK(state IN ('queued','processing','failed','needs_review')),
    created_at timestamptz NOT NULL DEFAULT now(), started_at timestamptz, finished_at timestamptz,
    error_code text, report jsonb,
    UNIQUE(document_id,attempt), FOREIGN KEY(organization_id,supplier_id,document_id) REFERENCES documents(organization_id,supplier_id,id),
    CHECK((state='needs_review')=(report IS NOT NULL)),CHECK((state='failed')=(error_code IS NOT NULL))
    ); CREATE INDEX processing_queue ON processing_attempts(created_at) WHERE state='queued'""")


def downgrade():
    op.execute("DROP TABLE processing_attempts")
