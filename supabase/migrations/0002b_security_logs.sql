-- =============================================================================
-- SMAReX :: 0002b :: security_logs
-- =============================================================================
-- Audit trail of every VirusTotal submission -- including uploads that were
-- rejected and therefore never stored.

create table public.security_logs (
    id                     uuid primary key default gen_random_uuid(),
    resource_id            uuid references public.resources (id) on delete set null,
    user_id                uuid references auth.users (id) on delete set null,
    file_name              text not null,
    file_size              bigint not null,
    file_hash              text not null,
    scan_status            public.scan_status not null default 'pending',
    scan_result            jsonb,
    scan_date              timestamptz not null default now(),
    details                text,
    virustotal_analysis_id text,
    created_at             timestamptz not null default now(),

    constraint security_logs_hash_format check (file_hash ~ '^[0-9a-f]{64}$')
);

create index security_logs_hash_idx     on public.security_logs (file_hash);
create index security_logs_status_idx   on public.security_logs (scan_status, scan_date desc);
create index security_logs_resource_idx on public.security_logs (resource_id);
create index security_logs_user_idx     on public.security_logs (user_id, scan_date desc);