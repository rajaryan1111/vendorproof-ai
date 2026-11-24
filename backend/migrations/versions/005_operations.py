from alembic import op

revision = "005_operations"
down_revision = "004_resolution"


def upgrade():
    op.execute("""
    ALTER TABLE documents ADD COLUMN scanned_digest text CHECK(scanned_digest=digest);
    ALTER TABLE processing_attempts ADD COLUMN available_at timestamptz NOT NULL DEFAULT now(),
      ADD COLUMN requested_by uuid, ADD FOREIGN KEY(requested_by,organization_id) REFERENCES memberships(user_id,organization_id);
    CREATE TABLE worker_health(singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
      seen_at timestamptz NOT NULL,ocr_ready boolean NOT NULL);
    CREATE INDEX documents_supplier_current ON documents(organization_id,supplier_id,created_at DESC) WHERE NOT archived;
    CREATE INDEX runs_supplier_recent ON verification_runs(organization_id,supplier_id,created_at DESC,id DESC);
    CREATE INDEX exceptions_by_org ON verification_findings(organization_id,created_at,id) WHERE requires_review;
    """)


def downgrade():
    op.execute("""DROP INDEX exceptions_by_org,runs_supplier_recent,documents_supplier_current;
    DROP TABLE worker_health;
    ALTER TABLE processing_attempts DROP COLUMN available_at, DROP COLUMN requested_by;
    ALTER TABLE documents DROP COLUMN scanned_digest""")
