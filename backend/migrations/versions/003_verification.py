from alembic import op

revision="003_verification"
down_revision="002_processing"

def upgrade():
    op.execute("""
    CREATE TABLE verification_policies(
      organization_id uuid NOT NULL,supplier_id uuid NOT NULL,version int NOT NULL,body jsonb NOT NULL,
      actor uuid NOT NULL REFERENCES users,created_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(organization_id,supplier_id,version), FOREIGN KEY(organization_id,supplier_id) REFERENCES suppliers(organization_id,id));
    CREATE TABLE verification_runs(
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),organization_id uuid NOT NULL,supplier_id uuid NOT NULL,
      policy_version int NOT NULL,rule_version text NOT NULL,as_of date NOT NULL,fingerprint text NOT NULL,
      inventory jsonb NOT NULL,checklist jsonb NOT NULL,actor uuid NOT NULL REFERENCES users,created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(organization_id,supplier_id,id), UNIQUE(organization_id,supplier_id,fingerprint),
      FOREIGN KEY(organization_id,supplier_id,policy_version) REFERENCES verification_policies);
    CREATE TABLE verification_findings(
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),organization_id uuid NOT NULL,supplier_id uuid NOT NULL,run_id uuid NOT NULL,
      rule text NOT NULL,outcome text NOT NULL,severity text NOT NULL,explanation text NOT NULL,quality text NOT NULL,
      requires_review boolean NOT NULL,evidence jsonb NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(organization_id,supplier_id,id),FOREIGN KEY(organization_id,supplier_id,run_id) REFERENCES verification_runs(organization_id,supplier_id,id));
    CREATE INDEX findings_by_run ON verification_findings(run_id);
    CREATE TABLE verification_reviews(seq bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,organization_id uuid NOT NULL,supplier_id uuid NOT NULL,
      finding_id uuid NOT NULL,actor uuid NOT NULL REFERENCES users, status text NOT NULL CHECK(status IN ('acknowledged','dismissed','resolved','clarification_requested')),
      reason text NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 500),created_at timestamptz NOT NULL DEFAULT now(),
      FOREIGN KEY(organization_id,supplier_id,finding_id) REFERENCES verification_findings(organization_id,supplier_id,id));
    CREATE INDEX reviews_by_finding ON verification_reviews(finding_id,seq DESC);
    CREATE FUNCTION vp_reject_history_change() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable verification history'; END $$;
    CREATE TRIGGER preserve_verification_review BEFORE UPDATE OR DELETE ON verification_reviews FOR EACH ROW EXECUTE FUNCTION vp_reject_history_change();
    """)

def downgrade():
    op.execute("DROP TABLE verification_reviews,verification_findings,verification_runs,verification_policies; DROP FUNCTION vp_reject_history_change()")
