-- =============================================================================
-- SMAReX :: seed.sql
-- =============================================================================
-- Reference data ONLY. No demo resources, users or comments are inserted:
-- every row in the platform originates from a real upload through the pipeline.
-- Safe to re-run.
--
--   psql "$DATABASE_URL" -f supabase/seed.sql
-- ============================================================================

-- Institutional email domains permitted to authenticate (IIUM Live).
-- Only the IIUM Live domain is accepted; every other row is removed so the
-- handle_new_user() trigger (0006) rejects sign-ups from any other domain.
insert into public.allowed_email_domains (domain, label) values
    ('live.iium.edu.my', 'IIUM Live - login domain')
on conflict (domain) do update set label = excluded.label;

delete from public.allowed_email_domains where domain <> 'live.iium.edu.my';