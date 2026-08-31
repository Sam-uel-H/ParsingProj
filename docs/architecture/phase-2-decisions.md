# Phase 2 architecture decisions

## Draft saves use one aggregate endpoint

The editor saves template metadata and its ordered columns together with
`PUT /templates/{id}/draft`. This keeps the browser form simple and lets the backend validate and
commit one consistent draft. Focused column create, update, and delete endpoints remain available
for API clients, but the visual editor does not need to coordinate several partial requests.

## Optimistic concurrency protects drafts

Each template version has an integer `lock_version`. A successful mutation increments it, and edit,
delete, and publish requests must send the value they loaded. The service also locks the current
version row while processing a mutation. A stale request receives a structured `409 Conflict`
containing the current lock value rather than silently overwriting another save.

## Publication is an immutable state transition

Publishing validates the complete draft before changing any state. It then records status,
publication time, and publishing user in the same database transaction. Database constraints keep
publication metadata consistent with status. All mutation services reject a published version.

Creating a new draft from a published version is not included here because the development plan
assigns version creation to Phase 8. Drag-and-drop ordering and the Prompt Helper are likewise left
for their planned later phases; Phase 2 uses explicit stable display order and plain prompt fields.
