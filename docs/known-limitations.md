# MVP Known Limitations

- Parsing uses the deterministic fake LLM provider. A production LLM adapter and credentials are
  intentionally deferred.
- The local extractor handles machine-readable PDF, DOCX, image preview, and UTF-8 text. It does
  not OCR scanned image text.
- Local object storage is filesystem-backed. Production S3-compatible storage is not configured.
- Extraction and parsing require Redis, Celery workers, and one Beat scheduler. Queued work is
  durable in PostgreSQL but waits when these services are unavailable. Windows needs Linux through
  WSL2/Docker; this machine's Linux service setup is still pending.
- A deterministic development identity is used. OIDC, RBAC, and audit hardening are deferred.
- Template columns support scalar values only; repeating tables and nested collections remain out of
  scope for the current release.
- Prompt Helper tags and prompt refinement are available with the deterministic local LLM provider.
  A production prompt-suggestion adapter and credentials are not configured. PDF text selection
  requires machine-readable text that maps uniquely to the extraction; OCR-only images cannot be
  tagged through the PDF text layer.
- Reprocessing preserves prior extraction versions. Tags and jobs retain their original extraction
  IDs. Historical jobs with ambiguous extraction provenance are not automatically backfilled.
- The 30-second SLA for 20 columns and 10 pages is the acceptance target. Synthetic-provider
  benchmarks do not establish production OCR/LLM performance. Context selection currently uses a
  character budget and field-name excerpts; production adapters must enforce model token limits.
- Parsing-result evidence highlighting, quality analytics, retention automation, and production
  monitoring remain post-MVP features.
- CSV and JSON exports are generated on demand and are not retained as stored artifacts.
