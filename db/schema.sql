-- ═══════════════════════════════════════════════════════════════
-- schema.sql
-- Run this ONCE to create all tables in your PostgreSQL database.
--
-- How to run:
--   psql -U postgres -d credit_card_agent_db -f schema.sql
-- Or paste into pgAdmin query tool.
-- ═══════════════════════════════════════════════════════════════


-- ── Create database (run this separately if DB doesn't exist yet) ─
-- CREATE DATABASE credit_card_agent_db;
-- \c credit_card_agent_db;


-- ── Enable UUID extension ─────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;


-- ═══════════════════════════════════════════════════════════════
-- TABLE 1: LEADS
-- Stores all potential customers to call.
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS leads (
    id                UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    name              VARCHAR(100) NOT NULL,
    phone             VARCHAR(15)  NOT NULL UNIQUE,
    age               INTEGER,
    income            NUMERIC(12, 2),          -- monthly income in INR
    credit_score      INTEGER,                  -- CIBIL score (300-900)
    employment_type   VARCHAR(50),              -- salaried | self_employed | business | student | retired
    city              VARCHAR(100),
    state             VARCHAR(100),
    language          VARCHAR(20)  DEFAULT 'english',  -- english | hindi | hinglish
    status            VARCHAR(30)  NOT NULL DEFAULT 'pending',
    -- pending | called | not_interested | applied | retry | unreachable
    priority_score    INTEGER      DEFAULT 50,  -- 0-100, higher = call first
    retry_count       INTEGER      DEFAULT 0,
    last_called_at    TIMESTAMP,
    notes             TEXT,
    source            VARCHAR(50)  DEFAULT 'manual',  -- manual | csv_import | api
    created_at        TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- Indexes for fast lead picking
CREATE INDEX IF NOT EXISTS idx_leads_status          ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_priority        ON leads(priority_score DESC);
CREATE INDEX IF NOT EXISTS idx_leads_phone           ON leads(phone);
CREATE INDEX IF NOT EXISTS idx_leads_status_priority ON leads(status, priority_score DESC);


-- ═══════════════════════════════════════════════════════════════
-- TABLE 2: CALLS
-- One record per outbound call attempt.
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS calls (
    id                UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    lead_id           UUID         NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    call_sid          VARCHAR(100),             -- Twilio call SID (Phase 3)
    start_time        TIMESTAMP    NOT NULL DEFAULT NOW(),
    end_time          TIMESTAMP,
    duration_seconds  INTEGER      DEFAULT 0,
    outcome           VARCHAR(30),
    -- connected | not_answered | busy | failed | completed | user_hangup
    recording_url     VARCHAR(500),             -- Twilio recording (Phase 3)
    created_at        TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_calls_lead_id   ON calls(lead_id);
CREATE INDEX IF NOT EXISTS idx_calls_outcome   ON calls(outcome);
CREATE INDEX IF NOT EXISTS idx_calls_start_time ON calls(start_time DESC);


-- ═══════════════════════════════════════════════════════════════
-- TABLE 3: APPLICATIONS
-- Stores everything collected during a call.
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS applications (
    id                UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    lead_id           UUID         NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    call_id           UUID         NOT NULL REFERENCES calls(id) ON DELETE CASCADE,

    -- Info collected during conversation
    income_stated     NUMERIC(12, 2),
    employment_type   VARCHAR(50),
    existing_cards    VARCHAR(200),             -- cards they already have
    spending_habits   TEXT,                     -- what they spend on

    -- Outcome
    card_recommended  VARCHAR(100),
    consent_given     BOOLEAN      NOT NULL DEFAULT FALSE,
    status            VARCHAR(30)  NOT NULL DEFAULT 'in_progress',
    -- in_progress | not_converted | applied | pending_kyc | approved | rejected

    -- Raw LLM data
    extracted_data    JSONB        DEFAULT '{}',  -- all fields extracted by LLM
    transcript        JSONB        DEFAULT '[]',  -- full conversation as JSON array

    -- Metrics
    objection_count   INTEGER      DEFAULT 0,
    turn_count        INTEGER      DEFAULT 0,

    created_at        TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_applications_lead_id      ON applications(lead_id);
CREATE INDEX IF NOT EXISTS idx_applications_call_id      ON applications(call_id);
CREATE INDEX IF NOT EXISTS idx_applications_status       ON applications(status);
CREATE INDEX IF NOT EXISTS idx_applications_consent      ON applications(consent_given);
CREATE INDEX IF NOT EXISTS idx_applications_extracted    ON applications USING gin(extracted_data);


-- ═══════════════════════════════════════════════════════════════
-- TABLE 4: TRANSCRIPTS
-- Stores each message of the conversation individually.
-- Useful for real-time saving and later analysis.
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS transcripts (
    id          UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    call_id     UUID         NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    speaker     VARCHAR(20)  NOT NULL,   -- agent | customer
    content     TEXT         NOT NULL,
    created_at  TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_transcripts_call_id    ON transcripts(call_id);
CREATE INDEX IF NOT EXISTS idx_transcripts_created_at ON transcripts(created_at);


-- ═══════════════════════════════════════════════════════════════
-- TABLE 5: CARD ISSUANCES
-- Tracks card issuance after application approval.
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS card_issuances (
    id               UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id   UUID         NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    card_type        VARCHAR(100) NOT NULL,
    status           VARCHAR(30)  NOT NULL DEFAULT 'pending',
    -- pending | issued | rejected | cancelled
    bank_reference   VARCHAR(100),             -- reference number from bank API
    issued_at        TIMESTAMP,
    rejection_reason VARCHAR(200),
    created_at       TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_card_issuances_app_id ON card_issuances(application_id);
CREATE INDEX IF NOT EXISTS idx_card_issuances_status ON card_issuances(status);


-- ═══════════════════════════════════════════════════════════════
-- TABLE 6: AUDIT LOG
-- Tracks every important status change for compliance.
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS audit_log (
    id           UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type  VARCHAR(50)  NOT NULL,   -- lead | call | application | card_issuance
    entity_id    VARCHAR(100) NOT NULL,
    action       VARCHAR(100) NOT NULL,   -- e.g. call_started, consent_given, card_issued
    details      JSONB        DEFAULT '{}',
    created_at   TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_entity       ON audit_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_created_at   ON audit_log(created_at DESC);


-- ═══════════════════════════════════════════════════════════════
-- TABLE 7: PROMPT LOGS
-- Logs every LLM call for debugging and quality monitoring.
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS prompt_logs (
    id              UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    call_id         VARCHAR(100),
    node_name       VARCHAR(50),              -- which LangGraph node called LLM
    model_used      VARCHAR(50),              -- groq / gemini / fallback
    prompt_length   INTEGER,
    response_length INTEGER,
    latency_ms      INTEGER,                  -- how long LLM took
    next_action     VARCHAR(30),              -- what LLM decided
    error           TEXT,                     -- null if successful
    created_at      TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prompt_logs_call_id    ON prompt_logs(call_id);
CREATE INDEX IF NOT EXISTS idx_prompt_logs_node_name  ON prompt_logs(node_name);
CREATE INDEX IF NOT EXISTS idx_prompt_logs_created_at ON prompt_logs(created_at DESC);


-- ═══════════════════════════════════════════════════════════════
-- AUTO-UPDATE updated_at TRIGGER
-- Automatically updates updated_at on any row change.
-- ═══════════════════════════════════════════════════════════════
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_leads_updated_at
    BEFORE UPDATE ON leads
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_calls_updated_at
    BEFORE UPDATE ON calls
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_applications_updated_at
    BEFORE UPDATE ON applications
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_card_issuances_updated_at
    BEFORE UPDATE ON card_issuances
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ═══════════════════════════════════════════════════════════════
-- VERIFY — list all created tables
-- ═══════════════════════════════════════════════════════════════
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
