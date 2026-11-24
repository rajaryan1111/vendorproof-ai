from alembic import op

revision = "006_member_access"
down_revision = "005_operations"


def upgrade():
    op.execute("""
    CREATE TABLE member_access_events (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        organization_id uuid NOT NULL REFERENCES organizations,
        actor uuid NOT NULL REFERENCES users,
        member_id uuid NOT NULL REFERENCES memberships,
        old_role text NOT NULL, new_role text NOT NULL,
        was_active boolean NOT NULL, is_active boolean NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX member_access_history ON member_access_events(organization_id, id DESC);
    CREATE TRIGGER preserve_member_access BEFORE UPDATE OR DELETE ON member_access_events
        FOR EACH ROW EXECUTE FUNCTION vp_reject_history_change();
    """)


def downgrade():
    op.execute("""
    DO $$ BEGIN IF EXISTS(SELECT FROM member_access_events) THEN
        RAISE EXCEPTION 'Member access history requires an archival plan';
    END IF; END $$;
    DROP TABLE member_access_events
    """)
