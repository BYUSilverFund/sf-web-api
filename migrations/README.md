# Chatbot schema history

- `001_chatbot_schema.sql`: earlier manifest/chunks design.
- `002_chatbot_ingestion_schema.sql`: current ingestion_state/embeddings baseline.
- `003_chatbot_fund_metadata.sql`: recovered metadata-only addition, retained for
  new database setup after 002. The original selector worktree called its combined
  baseline/metadata file `002_chatbot_fund_metadata.sql`; the active repository
  separates the metadata addition as 003 to avoid duplicate migration numbering.

**Do not execute either baseline or metadata migration against the intended
existing database for this recovery.** Its metadata schema and exact 109-row Quant
manual backfill were already applied on November 9, 2026. No migration ledger is
being rewritten and no migration is automatically applied by this change.

Original immutable review/application evidence remains in
`../../.fund-selector/sf-web-api/migrations/quant-fund-review/`, including
`application-report.md`, `apply-result.json`, `verification.json`, `dry-run.json`,
and the SQL reviewed at that time. Its historical proposed-only comments were
not rewritten. Restoring application code requires no database change.
