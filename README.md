# Document Parsing System

Phases 0 through 7 establish the complete MVP, Phase 8 adds the full template lifecycle, and
Phases 9-10 add Prompt Helper tagging and prompt refinement. The
system is a modular React/FastAPI application with PostgreSQL migrations,
provider boundaries, domain management, a visual template editor, secure document upload with local
object storage, canonical text extraction, page-by-page previews, parsing jobs, result review,
validated human corrections, CSV/JSON export, operational request tracing, and browser acceptance
coverage. Templates can be searched and filtered, versioned without changing identity, cloned,
archived, safely deleted when unused, and reordered while preserving historical jobs. Prompt Helper
links selected spans in a compatible sample document to draft template columns and stores expected
values against a specific extraction. Tagged examples can generate editable prompt suggestions,
which can be dry-run, compared with expected values, and accepted into a draft template version.

## Prerequisites

- Node.js 20 or newer
- Python 3.12 or newer
- Docker Desktop with Docker Compose (for PostgreSQL)

A native PostgreSQL 17 installation can be used instead of Docker when it exposes the databases
and credentials configured in `.env`.

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
npx playwright install chromium
```

The development credentials in `infra/docker-compose.yml` are local-only defaults. Do not
reuse them in a deployed environment.

Optional synthetic development data can be created after migration:

```powershell
cd apps/api
.\.venv\Scripts\python.exe -m app.seed
```

The seed command is idempotent, works only in `ENVIRONMENT=development`, and creates a published
Agent Bank Notice template without documents, secrets, or production data.

## Local configuration

| Setting | Development value | Purpose |
|---|---|---|
| `DATABASE_URL` | Local PostgreSQL URL | Application database |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed browser origin |
| `OBJECT_STORAGE_PATH` | `../../.local-storage` | Local original and preview storage |
| `MAX_UPLOAD_SIZE_BYTES` | `26214400` | Per-file upload limit |
| `EXTRACTION_TIMEOUT_SECONDS` | `30` | Extraction provider timeout |
| `LLM_TIMEOUT_SECONDS` | `30` | LLM provider timeout |
| `VALIDATION_RETRY_LIMIT` | `2` | Invalid extraction retries |
| `LLM_PROVIDER` | `fake` | Deterministic local parsing provider |
| `DOCUMENT_EXTRACTION_PROVIDER` | `local` | Local extraction implementation |
| `OBJECT_STORAGE_PROVIDER` | `filesystem` | Local storage implementation |
| `DEVELOPMENT_USER_*` | Synthetic local identity | Attribution before OIDC/RBAC |

Unsupported provider values fail configuration validation at startup. No provider secret is
required by the MVP configuration.

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
columns and extraction prompts, save it, and publish it. A published version is read-only; create
a successor draft version to make further edits. Local writes are attributed to the seeded
development identity configured in `.env`.

For a draft template with saved columns, open **Prompt Helper** from a column. Choose an extracted
sample document in the same domain, select text in the PDF text layer or extracted-text view, and
save an expected value. The page shows saved highlights and supports replacement and deletion.
The mapping must be unique within the selected page after whitespace normalization; ambiguous or
unmappable selections return an explicit error. Tags remain linked to the extraction used when
they were created. Generate a suggestion from a saved tag, edit and save it, then run it against
the sample document. The workspace compares the typed result with the expected value, shows
verified evidence when available, retains run history, and accepts the prompt into the current
draft template version. Unsaved edits prompt before switching columns or navigating away.

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

Use **Run parsing** to execute a published template against an extracted document. The result page
shows every template column in display order, highlights values that need review, lets a reviewer
save type-validated corrections, marks corrected values as human-verified, and exports reviewed
results as CSV or JSON. Exports use a reviewed value when present and otherwise fall back to the
original canonical parsing value.

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
npm run test:e2e
```

The Playwright suite starts the API and frontend automatically when they are not already running.
It performs the full synthetic Agent Bank Notice workflow and verifies empty and API failure states.

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
docs/architecture/        Decisions that constrain each completed phase
docs/known-limitations.md  Explicit MVP boundaries and deferred capabilities
infra/docker-compose.yml  Local PostgreSQL service
```

See `docs/architecture/` for the architecture choices made so far and the decisions intentionally
left for later phases. See `docs/known-limitations.md` before treating the MVP as a production
deployment.
