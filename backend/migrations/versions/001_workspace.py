from alembic import op

revision = "001_workspace"
down_revision = None


def upgrade():
    op.execute("""
    CREATE TABLE organizations(id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name text NOT NULL UNIQUE);
    CREATE TABLE users(id uuid PRIMARY KEY DEFAULT gen_random_uuid(), email text NOT NULL UNIQUE, password_hash text NOT NULL);
    CREATE TABLE memberships(id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users, organization_id uuid NOT NULL REFERENCES organizations, role text NOT NULL CHECK(role IN ('admin','operator','reviewer','auditor')), UNIQUE(user_id,organization_id));
    CREATE TABLE sessions(digest text PRIMARY KEY, membership_id uuid NOT NULL REFERENCES memberships ON DELETE CASCADE, expires_at timestamptz NOT NULL);
    CREATE TABLE suppliers(id uuid PRIMARY KEY DEFAULT gen_random_uuid(), organization_id uuid NOT NULL REFERENCES organizations, name varchar(160) NOT NULL CHECK(length(trim(name))>0), contact varchar(240) NOT NULL DEFAULT '', archived boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(), UNIQUE(organization_id,id));
    CREATE INDEX supplier_directory ON suppliers(organization_id,archived,name,id);
    CREATE TABLE documents(id uuid PRIMARY KEY, organization_id uuid NOT NULL, supplier_id uuid NOT NULL, filename varchar(160) NOT NULL, bytes integer NOT NULL CHECK(bytes>0), digest text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), archived boolean NOT NULL DEFAULT false, replaces uuid, UNIQUE(organization_id,supplier_id,id), FOREIGN KEY(organization_id,supplier_id) REFERENCES suppliers(organization_id,id), FOREIGN KEY(organization_id,supplier_id,replaces) REFERENCES documents(organization_id,supplier_id,id));
    CREATE TABLE activity(id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, organization_id uuid NOT NULL, supplier_id uuid NOT NULL, actor uuid NOT NULL REFERENCES users, action text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), FOREIGN KEY(organization_id,supplier_id) REFERENCES suppliers(organization_id,id));
    CREATE INDEX activity_recent ON activity(organization_id,id DESC);
    CREATE TABLE login_limits(key text PRIMARY KEY, starts timestamptz NOT NULL, attempts integer NOT NULL);
    """)


def downgrade():
    op.execute("DROP TABLE login_limits,activity,documents,suppliers,sessions,memberships,users,organizations")
