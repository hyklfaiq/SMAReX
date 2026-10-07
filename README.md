# SMAReX — Smart Academic Resource Exchange

An academic resource-sharing platform for IIUM students. Sign in with your IIUM
Live account, upload a PDF, and SMAReX will scan it with VirusTotal, store it
safely, extract its text with `pypdf` and generate an AI summary — then publish
it for others to search, rate, comment on and download.

---

## 1. Project overview

SMAReX uses a single sign-up/sign-in flow handled by Supabase Auth and
restricted to the IIUM Live domain (`@live.iium.edu.my`): students create
their own account from the login page, and the restriction is enforced by a
database trigger at sign-up and on every authenticated API request.

Users can browse, search and filter a shared library, download resources,
upload their own, rate and comment on them, and bookmark what is useful.
Administrators additionally manage users, moderate resources and review the
VirusTotal scan history.

## 2. Tech stack

| Layer | Technology |
|---|---|
| Frontend | Vite + React 18 + TypeScript |
| Styling | Tailwind CSS |
| UI components | shadcn/ui (Radix primitives) |
| Auth | Supabase Authentication (IIUM Live only) |
| Database | Supabase PostgreSQL |
| File storage | Supabase Storage (private bucket, signed URLs) |
| Backend | Python 3.11+ / FastAPI (async) |
| PDF text | `pypdf` |
| AI summaries | Hugging Face Inference API (`facebook/bart-large-cnn`) |
| File scanning | VirusTotal API v3 |

## 3. Architecture

```
Browser (React SPA)
   │  Supabase Auth  → access token
   │  fetch + Authorization: Bearer <token>
   ▼
FastAPI backend ──────────────── Supabase
   ├─ security/auth.py       verify JWT + IIUM domain      → Auth
   ├─ security/permissions   role + ownership checks
   ├─ virus_total/           upload → poll → verdict       → VirusTotal
   ├─ storage/               private bucket, signed URLs   → Supabase Storage
   ├─ pdf/                   pypdf text extraction
   ├─ ai/                    chunking + summarisation      → Hugging Face
   ├─ pipeline/              orchestrates the upload flow
   └─ api/v1/                routers                       → PostgreSQL
```

The backend connects with the service-role key and therefore bypasses RLS, so
it performs every authorisation check explicitly in
`app/security/permissions.py`. RLS policies remain in place as a second line of
defence for any direct client access.

The browser never receives a secret. It talks to Supabase Auth with the public
anon key and to the backend with a short-lived user access token; the
service-role key and the VirusTotal key exist only in backend environment
variables.

## 4. Prerequisites

* Python 3.11 or newer
* Node.js 18 or newer
* A Supabase project
* A VirusTotal API key (free tier is enough for development)

## 5. Installation

```bash
git clone <your-repo-url> smarex
cd smarex

# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

## 6. Environment variables

Real env files are git-ignored and are never committed; there are deliberately
no example files in the repository, so the full list lives here.

**`backend/.env`** — the values you must supply:

| Variable | Where it comes from |
|---|---|
| `DATABASE_URL` | Supabase → Settings → Database → Connection string |
| `SUPABASE_URL` | Supabase → Project Settings → API |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Project Settings → API (**server side only**) |
| `SUPABASE_JWT_SECRET` | Supabase → Settings → API → JWT Secret |
| `VIRUSTOTAL_API_KEY` | <https://www.virustotal.com/gui/user/<id>/apikey> |
| `ALLOWED_EMAIL_DOMAINS` | Must be `live.iium.edu.my` (IIUM Live only) |

Optional overrides such as `CORS_ORIGINS`, `MAX_UPLOAD_MB`, `AI_ENABLED`,
`HUGGINGFACE_API_KEY`, `STORAGE_BUCKET` and `LOG_LEVEL` all have safe defaults —
see `backend/app/core/config.py` for every setting.

**`frontend/.env.local`** — `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`.

Never commit a real key, and never put a secret in a `VITE_` variable: those are
compiled into the browser bundle and are readable by any visitor.

## 7. Supabase setup

### 7.1 Apply the database schema

Run the migrations in `supabase/migrations/` in filename order, then the seed:

```bash
# via the Supabase CLI
supabase db push

# or directly with psql
psql "$DATABASE_URL" -f supabase/migrations/0001_extensions_and_types.sql
psql "$DATABASE_URL" -f supabase/migrations/0002_tables_constraints_indexes.sql
psql "$DATABASE_URL" -f supabase/migrations/0002b_security_logs.sql
psql "$DATABASE_URL" -f supabase/migrations/0003_triggers.sql
psql "$DATABASE_URL" -f supabase/migrations/0004_rls_policies.sql
psql "$DATABASE_URL" -f supabase/migrations/0005_storage_policies.sql
psql "$DATABASE_URL" -f supabase/migrations/0006_auth_user_trigger.sql
psql "$DATABASE_URL" -f supabase/seed.sql
```

This creates seven tables — `profiles`, `resources`, `comments`, `ratings`,
`saved_resources`, `download_history`, `security_logs` — plus
`allowed_email_domains`, with all constraints, indexes, triggers and RLS
policies.

### 7.2 Storage bucket

Migration `0005_storage_policies.sql` creates a **private** bucket named
`resources`, limited to 25 MB per object and PDF MIME types only. Objects are
laid out as:

```
resources/{owner_id}/{resource_id}/{filename}
```

The first path segment is the owner id, which is what the object policies key
off, so a student's token can only read their own folder. There is
deliberately no anonymous policy and no update policy. Every download goes
through a short-lived signed URL minted by the backend after an authorisation
check.

If you create the bucket through the dashboard instead, set `public = false`
and apply the policies from that migration file.

### 7.3 Promote the first administrator

There is no self-service path to the admin role. After signing in once, run:

```sql
select public.promote_to_admin('your.email@live.iium.edu.my');
```

## 8. Authentication configuration

Access is limited to **@live.iium.edu.my** accounts, enforced in three places:

1. **Sign-up form.** The login page checks the domain before calling Supabase
   Auth and offers a "Create account" flow (full name, email, password).
2. **Database trigger.** `handle_new_user()` (migration `0006`) rejects any
   registration whose domain is absent from `public.allowed_email_domains`,
   which `seed.sql` keeps limited to `live.iium.edu.my`, and creates the
   matching `profiles` row.
3. **Backend.** Every authenticated request re-checks the domain against the
   `ALLOWED_EMAIL_DOMAINS` setting.

Enable email confirmation in Supabase → Authentication → Providers → Email so
new accounts must confirm their address before they can sign in.

## 9. VirusTotal setup

1. Sign in at <https://www.virustotal.com> and copy your API key from
   <https://www.virustotal.com/gui/user/<your-id>/apikey>.
2. Put it in `backend/.env` as `VIRUSTOTAL_API_KEY`.
3. Optionally tune `VIRUSTOTAL_REJECT_ON_MALICIOUS` and
   `VIRUSTOTAL_REJECT_ON_SUSPICIOUS`.

VirusTotal is an external file-analysis service. SMAReX does not claim any
specific detection technique on its behalf: it submits the file to the
`/api/v3/files` endpoint, polls `/api/v3/analyses/{id}` until the analysis
completes, and aggregates the published `stats` counters (`malicious`,
`suspicious`, `undetected`, `harmless`) into one accept/reject decision.

## 10. Hugging Face configuration

Summaries are generated with `facebook/bart-large-cnn` through the hosted
Inference API, so no model download is needed. An API token is optional; set
`HUGGINGFACE_API_KEY` to raise the rate limit.

To disable summarisation, set `AI_ENABLED=false` — files are still scanned,
stored and published, just without a summary.

## 11. Running the application

Two terminals:

```bash
# Terminal 1 - backend on http://127.0.0.1:8000
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload --port 8000

# Terminal 2 - frontend on http://localhost:5173
cd frontend
npm run dev
```

Open <http://localhost:5173>. Vite proxies `/api` to the backend, so the browser
stays on a single origin in development. Interactive API docs are at
<http://127.0.0.1:8000/docs> (disabled in production).

## 12. The upload pipeline

This is the core of the application, implemented in
`backend/app/pipeline/upload_pipeline.py`.

```
IIUM Live login
      │
      ▼
Metadata + PDF selected
      │
      ▼
1. Pre-flight validation -- extension, MIME, size, %PDF- magic bytes
      │                        (failure: nothing is sent anywhere)
      ▼
2. SHA-256 hash
      │
      ▼
3. VirusTotal scan -- upload, poll analysis, read verdict
      │
      +-- malicious / suspicious --> record in security_logs, store NOTHING,
      |                              return an error to the user
      |    (a scanner outage also fails closed: nothing is published)
      ▼
4. Supabase Storage upload          <-- the file exists only from here
      │
      ▼
5. resources row: publication_status = 'processing'
      │
      ▼
6. pypdf text extraction
      │
      ▼
7. Hugging Face summarisation (+ keywords)
      │
      ▼
8. Save summary to PostgreSQL
      │
      ▼
9. publication_status = 'published'  <-- visible in the library
```

Two properties matter, and both are enforced by the pipeline's ordering:

* **Nothing is stored before the scan passes.** A rejected upload never reaches
  Supabase Storage, is never summarised and is never visible to anyone. The
  verdict is still written to `security_logs` for administrators.
* **An AI failure never loses a stored file.** If extraction or the model fails,
  `ai_summary_status` becomes `failed`, the safely stored PDF is kept and the
  resource is still published. `POST /api/v1/resources/{id}/summary/retry`
  re-runs just that stage.

## 13. API reference

All endpoints sit under `/api/v1` and require `Authorization: Bearer <token>`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/auth/me` | Current profile and role |
| GET | `/auth/config` | Public login configuration |
| PUT | `/profile` | Update own academic details |
| GET | `/resources` | Browse, search, filter, sort, paginate |
| POST | `/resources` | Upload (multipart) - runs the full pipeline |
| GET | `/resources/{id}` | Resource details |
| DELETE | `/resources/{id}` | Delete own resource (or any, as admin) |
| GET | `/resources/{id}/download` | Authorised signed URL + history record |
| POST | `/resources/{id}/summary/retry` | Re-run summarisation |
| GET/POST | `/resources/{id}/comments` | List / add comments |
| DELETE | `/comments/{id}` | Delete own comment |
| GET/PUT/DELETE | `/resources/{id}/rating` | Read, set or clear your rating |
| GET | `/saved` | Your bookmarks |
| POST/DELETE | `/resources/{id}/save` | Bookmark / unbookmark |
| GET | `/admin/stats` | Dashboard counters |
| GET | `/admin/users` | List and search users |
| PUT | `/admin/users/{id}/role` | Change role, suspend or restore |
| GET | `/admin/resources` | All resources, including rejected |
| DELETE | `/admin/resources/{id}` | Moderate: remove a resource |
| GET | `/admin/security-logs` | VirusTotal verdict history |

Failures always use one envelope, with a message safe to show a user:

```json
{ "error": { "code": "malicious_file_rejected", "message": "...", "request_id": "..." } }
```

## 14. Security considerations

* **Secrets stay server-side.** Only the Supabase anon key reaches the browser,
  and it is designed to be public and backed by RLS. The service-role key and
  the VirusTotal key are read from backend environment variables only.
* **Fail-closed scanning.** If VirusTotal cannot be reached, the upload is
  rejected rather than published.
* **Layered file validation.** Extension, declared MIME type, declared size and
  the `%PDF-` magic bytes are all checked before anything is sent upstream, so a
  renamed executable never reaches the scanner. Filenames are reduced to a
  single safe path segment, which blocks path traversal.
* **Private storage.** The bucket is not public. Downloads require an
  authorisation check and use short-lived signed URLs.
* **Authorisation on every route.** Ownership and role are checked explicitly;
  a non-owner receives 404 rather than 403 so private items are not disclosed.
  Duplicate ratings are prevented by a database constraint, not only by code.
* **RLS as a second line of defence.** Policies confine the library to
  published + safe rows and security logs to administrators.
* **No leakage.** Unhandled errors return a generic message plus a request id;
  stack traces and third-party payloads stay in the server logs.
* **Production guard.** The backend refuses to start in `production` without the
  service-role key, JWT secret and VirusTotal key.

## 15. Deployment

**Backend** — any ASGI host (Render, Railway, Fly.io, Cloud Run):

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Set every variable from the table in section 6, including
`ENVIRONMENT=production`, the real `CORS_ORIGINS`, and the four secrets the
production validator insists on.

**Frontend** — build and host `dist/` on any static host:

```bash
npm run build      # emits dist/
```

Add a rewrite so every unknown path serves `index.html`, otherwise deep links
such as `/resources/<id>` will 404.

Before going live: apply the migrations, create the first admin with
`promote_to_admin`, and confirm the storage bucket is private.

## 16. Project layout

```
SMAREX/
├── supabase/
│   ├── migrations/     0001..0006, applied in order
│   └── seed.sql        allowed email domains (reference data only)
├── backend/
│   ├── app/
│   │   ├── api/        deps.py + v1 routers (auth, resources, interactions, admin)
│   │   ├── ai/         base, preprocess, inference_api, summarizer
│   │   ├── core/       config, errors, logging
│   │   ├── db/         async engine and session
│   │   ├── models/     SQLAlchemy ORM
│   │   ├── pdf/        pypdf extraction
│   │   ├── pipeline/   the upload pipeline
│   │   ├── schemas/    request/response models
│   │   ├── security/   auth, permissions, file validation, hashing
│   │   ├── storage/    Supabase Storage
│   │   ├── virus_total/  VirusTotal client
│   │   └── main.py     FastAPI app
└── frontend/
    └── src/
        ├── components/ ui/ (shadcn), layout, resource, common
        ├── contexts/   AuthContext
        ├── hooks/      TanStack Query hooks
        ├── layouts/    AppLayout
        ├── lib/        api client, supabase client, utils, constants
        ├── pages/      Login, Dashboard, Library, ResourceDetails,
        │               Upload, Saved, Profile, Admin, NotFound
        ├── types/      shared TypeScript types
        ├── App.tsx     routes and guards
        └── main.tsx
```