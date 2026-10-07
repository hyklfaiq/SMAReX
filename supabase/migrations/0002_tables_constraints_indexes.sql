-- =============================================================================
-- SMAReX :: 0002 :: Core tables, constraints and indexes
-- =============================================================================

-- ---------------------------------------------------------------------------
-- profiles -- mirrors auth.users, enriched with academic metadata
-- ---------------------------------------------------------------------------
create table public.profiles (
    id          uuid primary key references auth.users (id) on delete cascade,
    full_name   text        not null default '',
    email       text        not null,
    role        public.user_role not null default 'student',
    kulliyyah   text,
    programme   text,
    avatar_url  text,
    is_active   boolean     not null default true,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now(),

    constraint profiles_email_length check (char_length(email) between 3 and 320),
    constraint profiles_name_length check (char_length(full_name) <= 160)
);

create unique index profiles_email_key on public.profiles (lower(email));
create index profiles_role_idx      on public.profiles (role);
create index profiles_kulliyyah_idx on public.profiles (kulliyyah);

-- ---------------------------------------------------------------------------
-- resources -- one safely stored PDF plus its metadata and AI summary
-- ---------------------------------------------------------------------------
create table public.resources (
    id                 uuid primary key default gen_random_uuid(),
    owner_id           uuid not null references auth.users (id) on delete cascade,

    -- descriptive metadata supplied by the uploader
    title              text not null,
    description        text not null default '',
    subject            text not null,
    kulliyyah          text not null,
    category           text not null,
    semester           text,
    tags               text[] not null default '{}',

    -- storage metadata (Supabase Storage, private bucket)
    file_name          text not null,
    file_path          text not null,
    file_size          bigint not null,
    file_type          text not null default 'application/pdf',
    file_hash          text not null,

    -- pipeline state
    security_status    public.security_status    not null default 'pending',
    publication_status public.publication_status not null default 'draft',
    ai_summary_status  public.ai_summary_status  not null default 'pending',
    ai_summary         text,
    ai_keywords        text[] not null default '{}',
    ai_model           text,
    ai_summary_error   text,
    page_count         integer,

    -- denormalised counters, maintained by the backend
    download_count  integer not null default 0,
    view_count      integer not null default 0,
    rating_avg      numeric(3, 2) not null default 0,
    rating_count    integer not null default 0,
    is_flagged      boolean not null default false,

    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now(),

    -- integrity checks
    constraint resources_file_size_positive    check (file_size > 0),
    constraint resources_title_length          check (char_length(title) between 3 and 300),
    constraint resources_description_length    check (char_length(description) <= 8000),
    constraint resources_subject_length        check (char_length(subject) between 2 and 200),
    constraint resources_hash_format           check (file_hash ~ '^[0-9a-f]{64}$'),

    -- a published resource may never claim to be unscanned or unsafe
    constraint resources_published_must_be_safe
        check (publication_status <> 'published' or security_status = 'safe')
);

-- Only published + safe rows are ever served by these access paths.
create index resources_library_idx
    on public.resources (created_at desc)
    where publication_status = 'published' and security_status = 'safe';

create index resources_kulliyyah_idx on public.resources (kulliyyah);
create index resources_subject_idx   on public.resources (subject);
create index resources_category_idx  on public.resources (category);
create index resources_owner_idx     on public.resources (owner_id, created_at desc);
create index resources_tags_idx     on public.resources using gin (tags);
create index resources_file_hash_idx on public.resources (file_hash);
create index resources_flagged_idx   on public.resources (created_at desc) where is_flagged;

-- Block re-uploading a byte-identical PDF while a live copy already exists.
create unique index resources_active_file_hash_key
    on public.resources (file_hash)
    where security_status = 'safe' and publication_status <> 'deleted';
-- Full-text search surface: title, description, subject, kulliyyah, tags.
-- Plain column populated by a trigger, not a generated column:
-- array_to_string() is only STABLE, so Postgres rejects it as a
-- generated-column expression (error 42P17).
alter table public.resources
    add column search_vector tsvector;

create index resources_search_idx on public.resources using gin (search_vector);


-- ---------------------------------------------------------------------------
-- comments
-- ---------------------------------------------------------------------------
create table public.comments (
    id          uuid primary key default gen_random_uuid(),
    resource_id uuid not null references public.resources (id) on delete cascade,
    user_id     uuid not null references auth.users (id) on delete cascade,
    comment     text not null,
    is_hidden   boolean     not null default false,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now(),

    constraint comments_body_length check (char_length(comment) between 1 and 4000)
);

create index comments_resource_idx on public.comments (resource_id, created_at desc);
create index comments_user_idx     on public.comments (user_id, created_at desc);

-- ---------------------------------------------------------------------------
-- ratings -- one rating per user per resource
-- ---------------------------------------------------------------------------
create table public.ratings (
    id          uuid primary key default gen_random_uuid(),
    resource_id uuid not null references public.resources (id) on delete cascade,
    user_id     uuid not null references auth.users (id) on delete cascade,
    rating      smallint not null,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now(),

    constraint ratings_range check (rating between 1 and 5),
    constraint ratings_unique_per_user unique (resource_id, user_id)
);

create index ratings_resource_idx on public.ratings (resource_id);

-- ---------------------------------------------------------------------------
-- saved_resources -- bookmarks
-- ---------------------------------------------------------------------------
create table public.saved_resources (
    id          uuid primary key default gen_random_uuid(),
    resource_id uuid not null references public.resources (id) on delete cascade,
    user_id     uuid not null references auth.users (id) on delete cascade,
    created_at  timestamptz not null default now(),

    constraint saved_resources_unique unique (resource_id, user_id)
);

create index saved_resources_user_idx on public.saved_resources (user_id, created_at desc);

-- ---------------------------------------------------------------------------
-- download_history -- audit trail for every successful secure download
-- ---------------------------------------------------------------------------
create table public.download_history (
    id            uuid primary key default gen_random_uuid(),
    resource_id   uuid not null references public.resources (id) on delete cascade,
    user_id       uuid not null references auth.users (id) on delete cascade,
    downloaded_at timestamptz not null default now()
);

create index download_history_resource_idx on public.download_history (resource_id, downloaded_at desc);
create index download_history_user_idx     on public.download_history (user_id, downloaded_at desc);