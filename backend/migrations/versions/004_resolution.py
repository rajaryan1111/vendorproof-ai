from alembic import op

revision = "004_resolution"
down_revision = "003_verification"


def upgrade():
    op.execute("""
    ALTER TABLE memberships ADD COLUMN active boolean NOT NULL DEFAULT true;
    ALTER TABLE verification_reviews DROP CONSTRAINT verification_reviews_status_check,
      ADD CHECK(status IN ('assigned','open','in_progress','awaiting_supplier_response','awaiting_internal_review','reopened','acknowledged','dismissed','resolved','clarification_requested')),
      ADD COLUMN kind text NOT NULL DEFAULT 'decision' CHECK(kind IN ('decision','assignment','comparison')),
      ADD COLUMN from_state text, ADD COLUMN assignee uuid,
      ADD COLUMN compared_run uuid, ADD COLUMN correction_doc uuid,
      ADD FOREIGN KEY(assignee,organization_id) REFERENCES memberships(user_id,organization_id),
      ADD FOREIGN KEY(organization_id,supplier_id,compared_run) REFERENCES verification_runs(organization_id,supplier_id,id),
      ADD FOREIGN KEY(organization_id,supplier_id,correction_doc) REFERENCES documents(organization_id,supplier_id,id);
    CREATE INDEX assignment_latest ON verification_reviews(finding_id,seq DESC) WHERE kind='assignment';
    CREATE TABLE exception_drafts(organization_id uuid NOT NULL,supplier_id uuid NOT NULL,finding_id uuid NOT NULL,
      revision integer NOT NULL CHECK(revision>0),subject text NOT NULL,message text NOT NULL,actor uuid NOT NULL REFERENCES users,created_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(finding_id,revision), FOREIGN KEY(organization_id,supplier_id,finding_id) REFERENCES verification_findings(organization_id,supplier_id,id));
    CREATE TABLE exception_corrections(organization_id uuid NOT NULL,supplier_id uuid NOT NULL,finding_id uuid NOT NULL,
      request_id uuid NOT NULL,document_id uuid NOT NULL UNIQUE,actor uuid NOT NULL REFERENCES users,created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(finding_id,request_id),FOREIGN KEY(organization_id,supplier_id,finding_id) REFERENCES verification_findings(organization_id,supplier_id,id),
      FOREIGN KEY(organization_id,supplier_id,document_id) REFERENCES documents(organization_id,supplier_id,id));
    CREATE TRIGGER immutable_run BEFORE UPDATE OR DELETE ON verification_runs FOR EACH ROW EXECUTE FUNCTION vp_reject_history_change();
    CREATE TRIGGER immutable_finding BEFORE UPDATE OR DELETE ON verification_findings FOR EACH ROW EXECUTE FUNCTION vp_reject_history_change();
    CREATE INDEX corrections_by_finding ON exception_corrections(finding_id,created_at DESC);
    CREATE TRIGGER immutable_draft BEFORE UPDATE OR DELETE ON exception_drafts FOR EACH ROW EXECUTE FUNCTION vp_reject_history_change();
    CREATE TRIGGER immutable_correction BEFORE UPDATE OR DELETE ON exception_corrections FOR EACH ROW EXECUTE FUNCTION vp_reject_history_change();
    CREATE VIEW exception_queue AS SELECT f.organization_id,f.supplier_id,f.id,f.run_id,f.rule,f.outcome,f.severity,f.created_at,s.name AS supplier,s.archived,
    COALESCE(r.seq,0) AS revision,CASE r.status WHEN 'acknowledged' THEN 'in_progress' WHEN 'clarification_requested' THEN 'awaiting_supplier_response' ELSE COALESCE(r.status,'open') END AS status,
    a.assignee,u.email AS owner FROM verification_findings f JOIN suppliers s ON s.id=f.supplier_id AND s.organization_id=f.organization_id
    LEFT JOIN LATERAL(SELECT seq,status FROM verification_reviews WHERE finding_id=f.id ORDER BY seq DESC LIMIT 1) r ON true
    LEFT JOIN LATERAL(SELECT assignee FROM verification_reviews WHERE finding_id=f.id AND kind='assignment' ORDER BY seq DESC LIMIT 1) a ON true
    LEFT JOIN users u ON u.id=a.assignee WHERE f.requires_review;
    """)


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT FROM exception_drafts) OR EXISTS(SELECT FROM exception_corrections)
      OR EXISTS(SELECT FROM verification_reviews WHERE kind!='decision' OR from_state IS NOT NULL)
      OR EXISTS(SELECT FROM memberships WHERE NOT active) THEN RAISE EXCEPTION 'Phase 4 history present; downgrade requires an archival plan'; END IF; END $$;
    DROP TRIGGER immutable_run ON verification_runs;
    DROP TRIGGER immutable_finding ON verification_findings;
    DROP VIEW exception_queue;
    DROP TABLE exception_corrections,exception_drafts;
    ALTER TABLE verification_reviews DROP CONSTRAINT verification_reviews_status_check,
    ADD CHECK(status IN ('acknowledged','dismissed','resolved','clarification_requested')),
    DROP COLUMN kind,DROP COLUMN from_state,DROP COLUMN assignee,DROP COLUMN compared_run,DROP COLUMN correction_doc;
    ALTER TABLE memberships DROP COLUMN active""")
