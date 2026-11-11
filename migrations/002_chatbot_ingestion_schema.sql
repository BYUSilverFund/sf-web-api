-- Current ingestion/retrieval contract. Apply explicitly to an isolated dev database.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS chatbot;

CREATE TABLE IF NOT EXISTS chatbot.ingestion_state (
    document_key TEXT PRIMARY KEY,
    s3_bucket TEXT NOT NULL,
    s3_key TEXT NOT NULL,
    s3_version_id TEXT,
    s3_etag TEXT NOT NULL,
    s3_last_modified TIMESTAMPTZ NOT NULL,
    processing_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (processing_status IN ('pending', 'processing', 'indexed', 'failed', 'deleted')),
    last_successful_ingestion_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (s3_bucket, s3_key)
);

CREATE TABLE IF NOT EXISTS chatbot.embeddings (
    chunk_id TEXT PRIMARY KEY,
    document_key TEXT NOT NULL
        REFERENCES chatbot.ingestion_state (document_key) ON DELETE CASCADE,
    chunk_number INTEGER NOT NULL,
    page INTEGER NOT NULL,
    pdf_pages JSONB NOT NULL,
    excerpt TEXT NOT NULL,
    embedding VECTOR(1024) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (document_key, chunk_number)
);

CREATE INDEX IF NOT EXISTS embeddings_document_key_idx
    ON chatbot.embeddings (document_key);
