# Phase 11: Durable jobs and reprocessing

## Execution and recovery

Extraction and parsing endpoints commit queued work to PostgreSQL before publishing a Celery
message. `background_tasks` is the durable status record and dispatch outbox. Redis holds messages,
not application status. Celery uses late acknowledgments, worker-loss rejection, and a prefetch of one.
A Celery Beat sweep republishes due unfinished tasks every five seconds, with a 30-second dispatch
cooldown. Run one Beat scheduler. Broker outages leave recoverable queued rows in PostgreSQL.

A session-level PostgreSQL advisory lock serializes each task across workers and commits. Worker
death releases the lock. Completed tasks are no-ops on redelivery. Results and progress commit
together per completed provider group; retries skip persisted columns. Database uniqueness is a
second protection against duplicate results and invocation records. No database session is shared
across concurrently executing provider requests.

Attempts, progress, next retry time, and sanitized error classification are persisted. Timeouts,
transient failures, and rate limits receive bounded exponential backoff. Exhausted jobs fail visibly.
Provider adapters classify throttling using `RateLimitProviderError` and transient failures using
`RetryableProviderError`. Unexpected worker errors are retried within the same attempt budget.

## Versioning and API behavior

New parsing jobs pin the published template and successful extraction at submission time. Historical
jobs are backfilled only when a single successful extraction makes the link unambiguous. Otherwise
their extraction ID stays null; migration does not invent provenance.

Reprocessing creates a numbered extraction, preserving every prior extraction and its previews.
During reprocessing, the new current extraction is queued and new parsing is disabled until it
succeeds. Existing jobs keep using their original extraction. Repeated submissions while extraction
is active return the same task. Parsing accepts an optional UUID idempotency key scoped to the actor.

Creation endpoints retain their existing HTTP 200 response contracts but usually return queued
records. Clients must poll the saved resource. Recent jobs and versioned extraction history are
available through list endpoints. Review and export require a completed parsing job.

## Concurrency and context

`PARSING_CONCURRENCY` bounds simultaneous provider requests per worker task. Worker process count
multiplies this limit and must match provider capacity. The default is per-column execution; callers
can select batching. Batch responses are matched by column name, independent of response order.
Only invalid columns are included in validation retries. Batch token usage is attributed once.

`PARSING_CONTEXT_CHARACTERS` limits the character budget including prompts and a reserved overhead.
Oversize documents use field-name excerpts and a leading-text fallback. This is deliberately a
character cap, not an exact model-token guarantee. Production adapters must enforce their own model
token limits. No vector database is introduced.

## Verification and remaining acceptance

Database integration tests cover 20/50 columns, batching, request concurrency, duplicate delivery,
partial retries, broker failure, history, and extraction pinning. A Linux subprocess acceptance test
kills a worker and API, starts replacements, and checks that recovery preserves existing results.
Browser acceptance covers navigation back to saved jobs and extraction history.

The user-approved target is 30 seconds for 20 columns and 10 pages. Deterministic-provider timing is
an orchestration benchmark. Real-provider SLA acceptance remains pending approved OCR/LLM services.

Celery's supported runtime is Linux. Docker Compose supplies Redis, worker, and Beat with shared
filesystem storage. On this Windows machine, Docker/WSL is not installed yet; the attempted WSL
installation command did not enable it. Linux service startup requires completing that host setup.
