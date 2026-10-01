# Phase 7 Decisions

## MVP integration boundary

Phase 7 stabilizes the synchronous modular-monolith workflow delivered in Phases 0-6. It does not
introduce queues, Prompt Helper, RBAC, template lifecycle expansion, or production provider
adapters. Those remain assigned to later phases in `THE_PLAN.md`.

## Request tracing and logging

Every API response includes an `X-Request-ID` header. Structured API error bodies also include the
same request ID so a browser-visible failure can be matched to operational logs. A valid incoming
ID is preserved; otherwise the API generates one.

Ordinary request logs contain only method, URL path, status, duration, and request ID. Request
bodies, extracted document text, prompts, provider output, credentials, and query strings are not
logged. Unexpected exceptions are represented by type rather than their potentially sensitive
message.

## Error contract

Application errors, request validation errors, framework HTTP errors, and unexpected errors use a
single envelope:

```json
{
  "error": { "code": "not_found", "message": "Not Found" },
  "request_id": "correlation-id"
}
```

The browser displays the request ID when one is present.

## Development seed

`python -m app.seed` creates one synthetic Agent Bank Notices domain and one published Section 6
template. It is idempotent and refuses to run unless `ENVIRONMENT=development`. It does not create
documents, production records, secrets, or provider credentials.

## Database integration

Phase 7 adds indexes for parsing jobs by document and template version, parsing results by job and
validation status, LLM invocations by job, and published template lookup. It also adds checks for
retry/attempt counts and confidence range plus a unique invocation-attempt constraint.

## Acceptance boundary

Playwright drives the real browser workflow using a synthetic UTF-8 Agent Bank Notice. The notice
contains an invalid currency value so the deterministic provider exhausts retries and produces
`needs_review`. The test corrects that value and verifies both CSV and JSON exports. It also covers
browser refresh, an empty list, and a structured API failure state.
