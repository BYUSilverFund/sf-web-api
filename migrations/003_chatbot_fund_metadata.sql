-- Schema reference for NEW databases after 002_chatbot_ingestion_schema.sql.
-- Already applied to the intended database on 2026-11-09; DO NOT rerun there.
-- Original selector worktree called this 002_chatbot_fund_metadata.sql.
-- Metadata only: apply after review; no content/vector updates are performed here.
ALTER TABLE chatbot.embeddings ADD COLUMN IF NOT EXISTS fund TEXT;
ALTER TABLE chatbot.embeddings ADD COLUMN IF NOT EXISTS document_scope TEXT NOT NULL DEFAULT 'unassigned';
ALTER TABLE chatbot.embeddings ADD CONSTRAINT embeddings_fund_scope_check CHECK (
    (document_scope = 'fund' AND fund IS NOT NULL AND fund IN ('undergrad', 'quant', 'brigham_capital', 'grad', 'quant_paper'))
    OR (document_scope IN ('shared', 'unassigned') AND fund IS NULL)
);
