from alembic import op


revision = "a7c9e4f2b1d3"
down_revision = "9f4b2c8a1d6e"
branch_labels = None
depends_on = None


APP_ROLE = "givenaija_app"
APP_PASSWORD = "givenaija_app_password"


def upgrade() -> None:
    # Create a dedicated login role for the FastAPI application.
    # The role is deliberately NOT a superuser and does not own the tables.
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}'
            ) THEN
                CREATE ROLE {APP_ROLE}
                LOGIN
                PASSWORD '{APP_PASSWORD}'
                NOSUPERUSER
                NOCREATEDB
                NOCREATEROLE
                NOREPLICATION;
            END IF;
        END
        $$;
        """
    )

    # Allow the application role to access objects in the public schema.
    op.execute(
        f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}"
    )

    # Give the application normal CRUD access to application tables.
    op.execute(
        f"""
        GRANT SELECT, INSERT, UPDATE, DELETE
        ON TABLE
            users,
            members,
            campaigns,
            pledges,
            donations,
            receipts,
            idempotency_keys,
            accounts,
            journal_entries,
            journal_lines
        TO {APP_ROLE};
        """
    )

    # Audit records can be created and viewed by the application,
    # but the application must never be able to modify or remove them.
    op.execute(
        f"""
        GRANT SELECT, INSERT
        ON TABLE audit_log
        TO {APP_ROLE};
        """
    )

    op.execute(
        f"""
        REVOKE UPDATE, DELETE, TRUNCATE
        ON TABLE audit_log
        FROM {APP_ROLE};
        """
    )

    # Make sure future tables created by the migration owner receive
    # the appropriate application permissions.
    op.execute(
        f"""
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE, DELETE
        ON TABLES TO {APP_ROLE};
        """
    )




def downgrade() -> None:
    op.execute(
        f"REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM {APP_ROLE}"
    )

    op.execute(
        f"REVOKE USAGE ON SCHEMA public FROM {APP_ROLE}"
    )

    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}'
            ) THEN
                DROP ROLE {APP_ROLE};
            END IF;
        END
        $$;
        """
    )