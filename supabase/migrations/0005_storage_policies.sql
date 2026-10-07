-- =============================================================================
-- SMAReX :: 0005 :: Private storage bucket and object policies
-- =============================================================================
-- Bucket layout:  resources/{owner_id}/{resource_id}/{original_file_name}
--
-- The bucket is PRIVATE. Nothing is served through the public CDN endpoint;
-- the backend mints short-lived signed URLs after an authorisation check.

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
    'resources',
    'resources',
    false,
    26214400,                                     -- 25 MiB, mirrors MAX_UPLOAD_MB
    array['application/pdf', 'application/x-pdf']
)
on conflict (id) do update
    set public              = excluded.public,
        file_size_limit     = excluded.file_size_limit,
        allowed_mime_types  = excluded.allowed_mime_types;

-- The first path segment is the owner id for every object we create.
create or replace function public.storage_owner_id(object_name text)
returns uuid
language plpgsql
immutable
as $$
declare
    owner_segment text;
begin
    owner_segment := split_part(object_name, '/', 1);
    return owner_segment::uuid;
exception when others then
    return null;
end;
$$;

-- ---------------------------------------------------------------------------
-- Students may only touch objects inside their own folder.
-- ---------------------------------------------------------------------------
create policy "storage_objects_select_own_folder"
    on storage.objects for select
    to authenticated
    using (public.storage_owner_id(name) = (select auth.uid()));

create policy "storage_objects_insert_own_folder"
    on storage.objects for insert
    to authenticated
    with check (
        public.storage_owner_id(name) = (select auth.uid())
        and bucket_id = 'resources'
    );

create policy "storage_objects_delete_own_folder"
    on storage.objects for delete
    to authenticated
    using (public.storage_owner_id(name) = (select auth.uid()));

-- NOTE: no UPDATE policy and no anonymous policy are created on purpose.