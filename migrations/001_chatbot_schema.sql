-- Apply explicitly to the chatbot PostgreSQL database after enabling pgvector.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS chatbot;

CREATE TABLE IF NOT EXISTS chatbot.document_manifest (
    sharepoint_item_id TEXT PRIMARY KEY,
    source_path TEXT NOT NULL,
    etag TEXT,
    last_modified_at TIMESTAMPTZ,
    content_hash TEXT,
    s3_key TEXT,
    processing_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (processing_status IN ('pending', 'processing', 'indexed', 'failed')),
    last_successful_ingestion_at TIMESTAMPTZ,
    error_details TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chatbot.document_chunks (
    chunk_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sharepoint_item_id TEXT NOT NULL
        REFERENCES chatbot.document_manifest (sharepoint_item_id) ON DELETE CASCADE,
    document_key TEXT NOT NULL,
    page INTEGER,
    excerpt TEXT NOT NULL,
    embedding VECTOR(1024) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
