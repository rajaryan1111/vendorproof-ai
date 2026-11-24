-- Execute as the database owner after migrations, in the target database.
-- Create the peer-authenticated LOGIN role vendorproof separately.
SELECT current_database() AS target_db \gset
GRANT CONNECT ON DATABASE :"target_db" TO :"runtime_role";
GRANT USAGE ON SCHEMA public TO :"runtime_role";
GRANT SELECT ON ALL TABLES IN SCHEMA public TO :"runtime_role";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO :"runtime_role";
GRANT INSERT, UPDATE, DELETE ON sessions,login_limits TO :"runtime_role";
GRANT UPDATE(active,role) ON memberships TO :"runtime_role";
GRANT INSERT, UPDATE(archived,scanned_digest) ON documents TO :"runtime_role";
GRANT INSERT, UPDATE ON suppliers, processing_attempts, worker_health TO :"runtime_role";
GRANT INSERT ON member_access_events,activity,verification_policies,verification_runs,verification_findings,verification_reviews,exception_drafts,exception_corrections TO :"runtime_role";
