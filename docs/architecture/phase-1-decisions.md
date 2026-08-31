# Phase 1 Architecture Decisions

## Stable template identity and owned versions

`templates` stores the stable identity and its domain. Version-specific name, description, status,
and columns live under `template_versions`. Phase 1 creates version 1 in Draft status; it exposes no
publish operation. This keeps the data model compatible with immutable published versions in Phase 2.

## Development identity

API writes are attributed to a deterministic user configured through environment variables. The user
is created on the first write. This is deliberately not authentication; Phase 13 will replace the
dependency with verified OIDC identity while keeping the same user foreign keys.

## Column types and enum values

Column types use a PostgreSQL-backed application enum: String, Integer, Decimal, Currency, Date,
Boolean, and Enum. Enum values use JSONB for the scalar-only MVP. API validation and a database check
ensure only Enum columns carry a non-null value list. Canonical parsing value schemas remain Phase 5.

## Service boundaries

HTTP routers translate typed requests and responses. Domain/template services own transactions and
business invariants. SQLAlchemy models and database constraints provide a final integrity boundary.
No document, parsing, prompt-helper, publishing UI, or result behavior is included.

