-- =============================================================================
-- SMAReX :: 0006 :: auth.users bootstrap + IIUM Live domain restriction
-- =============================================================================
-- Creates a `profiles` row for every new auth user and rejects any sign-up
-- whose email domain is not on the allow-list. This is the database-level
-- enforcement of the "IIUM Live accounts only" rule; the backend repeats the
-- check on every authenticated request as defence in depth.

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    user_email  text := lower(new.email);
    user_domain text := split_part(coalesce(new.email, ''), '@', 2);
    domain_ok   boolean;
begin
    select exists (
        select 1 from public.allowed_email_domains d where d.domain = user_domain
    )
    into domain_ok;

    if not domain_ok then
        raise exception 'SMAReX: only institutional email addresses may register'
            using errcode = 'check_violation';
    end if;

    insert into public.profiles (id, full_name, email, role)
    values (
        new.id,
        coalesce(
            nullif(new.raw_user_meta_data ->> 'full_name', ''),
            nullif(new.raw_user_meta_data ->> 'name', ''),
            split_part(coalesce(new.email, ''), '@', 1)
        ),
        user_email,
        'student'
    )
    on conflict (id) do nothing;

    return new;
end;
$$;

create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------------
-- Administrator promotion. Run this as the service-role / SQL editor after the
-- account exists; there is deliberately no self-service path to `admin`.
-- ---------------------------------------------------------------------------
create or replace function public.promote_to_admin(target_email text)
returns public.profiles
language plpgsql
security definer
set search_path = public
as $$
declare
    result public.profiles;
begin
    update public.profiles
       set role = 'admin'
     where lower(email) = lower(target_email)
    returning * into result;

    if result.id is null then
        raise exception 'SMAReX: no profile found for %', target_email
            using errcode = 'no_data_found';
    end if;

    -- Mirror the role into auth metadata so JWT claims stay consistent.
    update auth.users
       set raw_app_meta_data = coalesce(raw_app_meta_data, '{}'::jsonb)
                             || jsonb_build_object('role', 'admin')
     where id = result.id;

    return result;
end;
$$;

revoke all on function public.promote_to_admin(text) from public, anon, authenticated;
grant execute on function public.promote_to_admin(text) to service_role;