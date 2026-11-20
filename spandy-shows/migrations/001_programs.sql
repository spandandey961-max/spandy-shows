-- Spandy Shows persistent program/source links; compatible with PostgreSQL and SQLite.
CREATE TABLE IF NOT EXISTS programs (
    id VARCHAR(64) PRIMARY KEY,
    payload TEXT NOT NULL,
    created_at BIGINT NOT NULL,
    expires_at BIGINT NOT NULL,
    kind VARCHAR(16) NOT NULL
);
CREATE INDEX IF NOT EXISTS programs_expiration ON programs(expires_at);
