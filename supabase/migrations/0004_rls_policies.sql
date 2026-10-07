-- =============================================================================
-- SMAReX :: 0004 :: Row Level Security
-- =============================================================================
-- The backend connects with the service-role key and therefore bypasses RLS,
-- so it performs its own authorisation in app/security/permissions.py. RLS is
-- the second line of defence for any direct client access with a user JWT.

-- ---------------------------------------------------------------------------
-- Helpers. SECURITY DEFINER avoids infinite recursion when a policy on
-- `profiles` needs to read `profiles`.
-- ---------------------------------------------------------------------------
create or replace function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select exists (
        select 1 from public.profiles
         where id = auth.uid()
           and role = 'admin'
           and is_active
    );
$$;

-- True only for rows the public library is allowed to serve.
create or replace function public.is_library_visible(
    p_publication public.publication_status,
    p_security    public.security_status
)
returns boolean
language sql
immutable
as $$
    select p_publication = 'published' and p_security = 'safe';
$$;

-- ---------------------------------------------------------------------------
-- profiles
-- ---------------------------------------------------------------------------
alter table public.profiles enable row level security;

create policy "profiles_select_own"
    on public.profiles for select
    to authenticated
    using (id = (select auth.uid()) or public.is_admin());

create policy "profiles_update_own"
    on public.profiles for update
    to authenticated
    using (id = (select auth.uid()))
    with check (id = (select auth.uid()));

-- The role column must not be self-editable; the trigger and admin paths own it.
create policy "profiles_admin_all"
    on public.profiles for all
    to authenticated
    using (public.is_admin())
    with check (public.is_admin());

-- ---------------------------------------------------------------------------
-- resources
-- ---------------------------------------------------------------------------
alter table public.resources enable row level security;

create policy "resources_select_library"
    on public.resources for select
    to authenticated
    using (public.is_library_visible(publication_status, security_status));

create policy "resources_select_own"
    on public.resources for select
    to authenticated
    using (owner_id = (select auth.uid()));

create policy "resources_insert_own"
    on public.resources for insert
    to authenticated
    with check (owner_id = (select auth.uid()));

create policy "resources_update_own"
    on public.resources for update
    to authenticated
    using (owner_id = (select auth.uid()))
    with check (owner_id = (select auth.uid()));

create policy "resources_delete_own"
    on public.resources for delete
    to authenticated
    using (owner_id = (select auth.uid()));

create policy "resources_admin_all"
    on public.resources for all
    to authenticated
    using (public.is_admin())
    with check (public.is_admin());

-- ---------------------------------------------------------------------------
-- comments
-- ---------------------------------------------------------------------------
alter table public.comments enable row level security;

create policy "comments_select_visible"
    on public.comments for select
    to authenticated
    using (
        not is_hidden
        or user_id = (select auth.uid())
        or public.is_admin()
    );

create policy "comments_insert_own"
    on public.comments for insert
    to authenticated
    with check (user_id = (select auth.uid()));

create policy "comments_update_own"
    on public.comments for update
    to authenticated
    using (user_id = (select auth.uid()) or public.is_admin());

create policy "comments_delete_own"
    on public.comments for delete
    to authenticated
    using (user_id = (select auth.uid()) or public.is_admin());

-- ---------------------------------------------------------------------------
-- ratings
-- ---------------------------------------------------------------------------
alter table public.ratings enable row level security;

create policy "ratings_select_all"
    on public.ratings for select
    to authenticated
    using (true);

create policy "ratings_insert_own"
    on public.ratings for insert
    to authenticated
    with check (user_id = (select auth.uid()));

create policy "ratings_update_own"
    on public.ratings for update
    to authenticated
    using (user_id = (select auth.uid()) or public.is_admin());

create policy "ratings_delete_own"
    on public.ratings for delete
    to authenticated
    using (user_id = (select auth.uid()) or public.is_admin());

-- ---------------------------------------------------------------------------
-- saved_resources -- strictly private to the bookmarking user
-- ---------------------------------------------------------------------------
alter table public.saved_resources enable row level security;

create policy "saved_resources_select_own"
    on public.saved_resources for select
    to authenticated
    using (user_id = (select auth.uid()));

create policy "saved_resources_insert_own"
    on public.saved_resources for insert
    to authenticated
    with check (user_id = (select auth.uid()));

create policy "saved_resources_delete_own"
    on public.saved_resources for delete
    to authenticated
    using (user_id = (select auth.uid()));

-- ---------------------------------------------------------------------------
-- download_history -- own trail readable, writes are server-side only
-- ---------------------------------------------------------------------------
alter table public.download_history enable row level security;

create policy "download_history_select_own"
    on public.download_history for select
    to authenticated
    using (user_id = (select auth.uid()) or public.is_admin());

-- ---------------------------------------------------------------------------
-- security_logs -- administrators only.
-- ---------------------------------------------------------------------------
alter table public.security_logs enable row level security;

create policy "security_logs_admin_select"
    on public.security_logs for select
    to authenticated
    using (public.is_admin());

-- ---------------------------------------------------------------------------
-- allowed_email_domains -- readable so the login screen can explain the rule
-- ---------------------------------------------------------------------------
alter table public.allowed_email_domains enable row level security;

create policy "allowed_domains_select"
    on public.allowed_email_domains for select
    to authenticated
    using (true);
