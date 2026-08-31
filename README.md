# Document Parsing System

Phases 0 through 4 establish a modular React/FastAPI application with PostgreSQL migrations,
provider boundaries, domain management, a visual template editor, and secure document upload with
local object storage, canonical text extraction, and page-by-page previews. Parsing jobs and later
workflow features are intentionally not implemented yet.

## Prerequisites

- Node.js 20 or newer
- Python 3.12 or newer
- Docker Desktop with Docker Compose (for PostgreSQL)

## One-time setup

From the repository root:

```powershell
Copy-Item .env.example .env

docker compose -f infra/docker-compose.yml up -d postgres

cd apps/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
alembic upgrade head

cd ../web
npm install
```

The development credentials in `infra/docker-compose.yml` are local-only defaults. Do not
reuse them in a deployed environment.

## Run locally

Start the backend in one terminal:

```powershell
cd apps/api
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Start the frontend in a second terminal:

```powershell
cd apps/web
npm run dev
```

Open <http://localhost:5173>. The page reports whether it can reach the backend. You can also
check <http://localhost:8000/health>, <http://localhost:8000/ready>, and the generated API docs
at <http://localhost:8000/docs>.

Uploaded originals are written beneath `.local-storage/` by the development filesystem provider;
only metadata and object keys are stored in PostgreSQL. Configure `MAX_UPLOAD_SIZE_BYTES` and
`OBJECT_STORAGE_PATH` in `.env` when different local values are needed. The storage provider
boundary remains compatible with a later organization-approved S3-compatible adapter.

Use **Domains** to create and list domains. Then open **Templates**, create a draft, add typed
columns and extraction prompts, save it, and publish it. A published version is read-only; creating
a successor version is deliberately left for Phase 8. Local writes are attributed to the seeded
development identity configured in `.env`.

Use **Documents** to select one or more PDF, DOCX, TIFF, PNG, JPG, or UTF-8 text files. A domain is
optional. Each file has its own progress and result, so an invalid file does not discard successful
files from the same selection. Document detail shows upload metadata, checksum, pending processing
status, and an original-file download. Uploads made through the web interface automatically trigger
the configured extractor, and pending API uploads can be started from Document Detail or the
document extraction endpoint.

Document Detail provides page navigation, 50–200% zoom, page previews, and extracted-text
inspection. The local provider extracts text from text PDFs, DOCX, and UTF-8 text, and generates
image/TIFF previews. It deliberately does not claim OCR capability: scanned-image text extraction
requires an approved `DocumentExtractionProvider` adapter before FR-1.3 is production-complete.

Example API workflow:

```powershell
$domain = Invoke-RestMethod -Method Post -Uri http://localhost:8000/domains `
  -ContentType application/json -Body '{"name":"Agent Bank Notices"}'

$templateBody = @{
  domain_id = $domain.id
  name = "Interest Notice"
  columns = @(
    @{ name = "Notice Date"; column_type = "date"; prompt_text = "Extract the notice date."; display_order = 0 }
    @{ name = "Interest Amount"; column_type = "currency"; prompt_text = "Extract the interest amount."; display_order = 1 }
  )
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post -Uri http://localhost:8000/templates `
  -ContentType application/json -Body $templateBody
```

Publishing requires at least one column and a non-empty extraction prompt for every column. The
editor sends the version's `lock_version` with saves and publishes, so a stale browser tab receives
a `409 Conflict` instead of overwriting newer work.

## Verification commands

Backend:

```powershell
cd apps/api
.\.venv\Scripts\Activate.ps1
ruff check app tests
pyright
pytest
alembic upgrade head
alembic current
```

PostgreSQL integration tests run when `TEST_DATABASE_URL` points to a disposable test database:

```powershell
docker compose -f ../../infra/docker-compose.yml exec postgres `
  createdb -U parsing parsing_test
$env:TEST_DATABASE_URL="postgresql+psycopg://parsing:parsing@localhost:5432/parsing_test"
pytest
```

The integration tests truncate their target tables. Never point `TEST_DATABASE_URL` at a database
containing data you want to keep.

Frontend:

```powershell
cd apps/web
npm run lint
npm run typecheck
npm test
npm run build
```

Database readiness:

```powershell
Invoke-RestMethod http://localhost:8000/ready
docker compose -f infra/docker-compose.yml exec postgres pg_isready -U parsing -d parsing
```

Stop local PostgreSQL without deleting its data:

```powershell
docker compose -f infra/docker-compose.yml stop postgres
```

## Repository layout

```text
apps/web/                 React + TypeScript + Vite browser application
apps/api/app/             FastAPI modular monolith, business modules, and provider contracts
apps/api/alembic/         SQLAlchemy migration environment and baseline
apps/api/tests/           API and provider contract tests
apps/web/src/features/    Domain, template, and document browser workflows
docs/architecture/        Decisions that constrain the Phase 0 foundation
infra/docker-compose.yml  Local PostgreSQL service
```

See `docs/architecture/phase-0-decisions.md`, `docs/architecture/phase-1-decisions.md`, and
`docs/architecture/phase-2-decisions.md` for the architecture choices made so far and the decisions
intentionally left for later phases. Phase 3 upload/storage choices are documented in
`docs/architecture/phase-3-decisions.md`.
