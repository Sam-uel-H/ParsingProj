# Phase 0 Architecture Decisions

This note records only decisions that constrain the foundation. Feature-specific decisions
remain with the phase that first needs them.

## Modular monolith

The backend is one FastAPI application. Cross-cutting code lives in `core`, database setup in
`db`, HTTP endpoints in `api`, and external integrations in `providers`. Later business modules
will own their routes, services, models, and rules rather than placing business logic in generic
helpers. A future worker may reuse these modules without creating microservices.

## Configuration and runtime boundaries

Runtime configuration comes from environment variables, optionally loaded from a local `.env`.
No real OCR or LLM key is required. Ordinary logs contain operational metadata only; provider
payloads and document text must not be logged.

## PostgreSQL and migration conventions

PostgreSQL is the primary database. SQLAlchemy 2 is used by the application and Alembic owns all
schema changes. Constraint names follow a shared naming convention so future migrations are
predictable. Future entity identifiers use application-generated UUIDv4 values, and timestamps
are timezone-aware UTC values with database defaults. The Phase 0 migration is intentionally
empty because business entities begin in Phase 1.

## Provider contracts

LLM, document extraction, and object storage are internal asynchronous interfaces. Their data
contracts contain only provider-neutral types. Document extraction is layout-aware: pages and
ordered text blocks preserve offsets and can later carry polygons and confidence values. The LLM
contract supports prompt suggestion and one-or-many column extraction with model and usage
metadata. Missing extracted values are represented as `None`; validation and canonical business
value representations belong to the parsing phase.

Deterministic in-memory fakes are the default for development and automated tests. This prevents
accidental external transmission of documents and makes tests repeatable.

## Deferred decisions

- MinIO/S3 adapter details are deferred until document upload in Phase 3.
- Production OCR and LLM vendors, confidential-content audit storage, and retry policies require
  stakeholder approval and are deferred to their owning phases.
- Background jobs and idempotency are deferred until long-running work exists.
- Template versioning, scalar value schemas, and result/audit persistence are documented in the
  roadmap but will be finalized alongside the corresponding business models.

