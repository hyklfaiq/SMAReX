-- =============================================================================
-- SMAReX :: 0001 :: Extensions and enumerated types
-- =============================================================================
-- Applied in order. Safe to re-run only on a fresh database.

create extension if not exists "pgcrypto";

-- Role of a platform user. `admin` is granted manually (see README -> Bootstrap).
create type public.user_role as enum ('student', 'admin');

-- Result of the VirusTotal file analysis for a resource.
create type public.security_status as enum (
    'pending',    -- accepted for scanning, analysis not started
    'scanning',   -- analysis submitted to VirusTotal, awaiting verdict
    'safe',       -- no engine reported the file as malicious or suspicious
    'malicious',  -- at least one engine classified the file as malicious
    'suspicious', -- at least one engine raised a non-malicious risk flag
    'error'       -- VirusTotal was unreachable / the analysis could not complete
);

-- Visibility lifecycle. A resource only becomes visible once it is `safe`.
create type public.publication_status as enum (
    'draft',      -- created, not yet processed
    'processing', -- stored safely; extraction / summarisation in flight
    'published',  -- visible in the public library
    'rejected',   -- withheld after a failed security analysis
    'deleted'     -- soft deleted by its owner or by an admin
);

-- AI summarisation outcome. Independent of publication status on purpose:
-- a summarisation failure must never hide or destroy a safely stored PDF.
create type public.ai_summary_status as enum (
    'pending',    -- queued
    'processing', -- extraction / model call in flight
    'completed',  -- summary + keywords persisted
    'skipped',    -- no usable text (empty or scanned PDF)
    'failed'      -- extraction or model error, see ai_summary_error
);

create type public.scan_status as enum (
    'pending',
    'scanning',
    'safe',
    'malicious',
    'suspicious',
    'error'
);