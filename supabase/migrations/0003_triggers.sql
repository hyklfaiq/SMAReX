-- =============================================================================
-- SMAReX :: 0003 :: Triggers
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Generic updated_at maintenance
-- ---------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at := now();
    return new;
end;
$$;

create trigger profiles_set_updated_at
    before update on public.profiles
    for each row execute function public.set_updated_at();

create trigger resources_set_updated_at
    before update on public.resources
    for each row execute function public.set_updated_at();

create trigger comments_set_updated_at
    before update on public.comments
    for each row execute function public.set_updated_at();

create trigger ratings_set_updated_at
    before update on public.ratings
    for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- Keep resources.rating_avg / rating_count consistent with the ratings table.
-- Runs for every insert, update and delete so the aggregate cannot drift.
-- ---------------------------------------------------------------------------
create or replace function public.refresh_resource_rating()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    target_resource uuid := coalesce(new.resource_id, old.resource_id);
begin
    update public.resources r
       set rating_avg = coalesce(agg.avg_rating, 0),
           rating_count = coalesce(agg.total, 0)
      from (
            select round(avg(rt.rating)::numeric, 2) as avg_rating,
                   count(*)                       as total
              from public.ratings rt
             where rt.resource_id = target_resource
           ) agg
     where r.id = target_resource;

    return coalesce(new, old);
end;
$$;

create trigger ratings_refresh_resource
    after insert or update or delete on public.ratings
    for each row execute function public.refresh_resource_rating();

-- ---------------------------------------------------------------------------
-- Bump resources.download_count from the download audit trail.
-- ---------------------------------------------------------------------------
create or replace function public.refresh_resource_download_count()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    update public.resources
       set download_count = download_count + 1
     where id = new.resource_id;

    return new;
end;
$$;

create trigger downloads_refresh_resource
    after insert on public.download_history
    for each row execute function public.refresh_resource_download_count();

-- ---------------------------------------------------------------------------
-- Keep resources.search_vector in step with the searchable columns.
-- A trigger rather than a generated column because array_to_string() is only
-- STABLE, and Postgres requires IMMUTABLE generated expressions (error 42P17).
-- ---------------------------------------------------------------------------
create or replace function public.set_resource_search_vector()
returns trigger
language plpgsql
as $$
begin
    new.search_vector :=
        setweight(to_tsvector('simple', coalesce(new.title, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(new.subject, '')), 'B') ||
        setweight(to_tsvector('simple', coalesce(new.kulliyyah, '')), 'B') ||
        setweight(to_tsvector('simple', coalesce(new.category, '')), 'C') ||
        setweight(to_tsvector('simple', coalesce(new.description, '')), 'C') ||
        setweight(
            to_tsvector('simple', coalesce(array_to_string(new.tags, ' '), '')), 'C'
        );
    return new;
end;
$$;

create trigger resources_set_search_vector
    before insert or update on public.resources
    for each row execute function public.set_resource_search_vector();

-- ---------------------------------------------------------------------------
-- Allow-list of email domains permitted to hold an account.
-- Editable without a migration: INSERT/DELETE rows as the university changes.
-- ---------------------------------------------------------------------------
create table public.allowed_email_domains (
    domain     text primary key,
    label      text,
    created_at timestamptz not null default now(),

    -- Domains are stored bare ('iium.edu.my'), which is the canonical form the
    -- backend compares against: it takes rsplit('@', 1)[-1] from the email and
    -- strips any leading '@' from the configured allow-list.
    constraint allowed_email_domains_format check (
        domain = lower(domain) and domain like '%.%' and domain <> ''
    )
);

comment on table public.allowed_email_domains is
    'IIUM Live domains allowed to authenticate. A sign-up whose email domain is absent here is rejected by handle_new_user().';