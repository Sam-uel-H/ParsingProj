# MVP Known Limitations

- Parsing uses the deterministic fake LLM provider. A production LLM adapter and credentials are
  intentionally deferred.
- The local extractor handles machine-readable PDF, DOCX, image preview, and UTF-8 text. It does
  not OCR scanned image text.
- Local object storage is filesystem-backed. Production S3-compatible storage is not configured.
- Extraction and parsing run synchronously in API requests. Durable queues arrive after the MVP.
- A deterministic development identity is used. OIDC, RBAC, and audit hardening are deferred.
- Template columns support scalar values only; repeating tables and nested collections remain out of
  scope for the current release.
- Prompt Helper tags and prompt refinement are available with the deterministic local LLM provider.
  A production prompt-suggestion adapter and credentials are not configured. PDF text selection
  requires machine-readable text that maps uniquely to the extraction; OCR-only images cannot be
  tagged through the PDF text layer.
- Existing documents cannot be reprocessed by the current API. Tags retain their original
  extraction ID, and a future reprocessing workflow must not silently move them.
- Parsing-result evidence highlighting, quality analytics, retention automation, and production
  monitoring remain post-MVP features.
- CSV and JSON exports are generated on demand and are not retained as stored artifacts.
