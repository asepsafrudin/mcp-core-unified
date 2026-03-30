-- Canonical correspondence schema (end-to-end normalization)

CREATE TABLE IF NOT EXISTS correspondence_letters (
    id BIGSERIAL PRIMARY KEY,
    source_namespace TEXT NOT NULL,
    source_sheet_id TEXT,
    source_range TEXT,
    source_row_num INTEGER,

    source_type TEXT NOT NULL CHECK (source_type IN ('internal', 'external', 'outgoing')),
    letter_number TEXT,
    letter_date DATE,
    received_date DATE,

    sender TEXT,
    recipient TEXT,
    subject TEXT,
    position_raw TEXT,
    disposition_raw TEXT,
    status TEXT,

    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    dedupe_key TEXT NOT NULL,
    synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (dedupe_key)
);

CREATE INDEX IF NOT EXISTS idx_correspondence_letters_source_type
    ON correspondence_letters (source_type);

CREATE INDEX IF NOT EXISTS idx_correspondence_letters_letter_date
    ON correspondence_letters (letter_date DESC);

CREATE INDEX IF NOT EXISTS idx_correspondence_letters_received_date
    ON correspondence_letters (received_date DESC);

CREATE INDEX IF NOT EXISTS idx_correspondence_letters_sender
    ON correspondence_letters (sender);

CREATE INDEX IF NOT EXISTS idx_correspondence_letters_subject_gin
    ON correspondence_letters
    USING gin (to_tsvector('simple', COALESCE(subject, '')));


CREATE TABLE IF NOT EXISTS correspondence_events (
    id BIGSERIAL PRIMARY KEY,
    letter_id BIGINT NOT NULL REFERENCES correspondence_letters(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL CHECK (event_type IN ('position', 'disposition', 'status')),
    event_value TEXT NOT NULL,
    event_at TIMESTAMPTZ,
    event_meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_correspondence_events_letter_id
    ON correspondence_events(letter_id);

CREATE INDEX IF NOT EXISTS idx_correspondence_events_event_type
    ON correspondence_events(event_type);


CREATE TABLE IF NOT EXISTS correspondence_sync_runs (
    id BIGSERIAL PRIMARY KEY,
    source_namespace TEXT NOT NULL,
    source_file TEXT,
    total_rows INTEGER NOT NULL DEFAULT 0,
    inserted_rows INTEGER NOT NULL DEFAULT 0,
    updated_rows INTEGER NOT NULL DEFAULT 0,
    skipped_rows INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    notes TEXT
);
