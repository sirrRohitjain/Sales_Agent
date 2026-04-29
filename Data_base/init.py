from connection import get_db_connection
def create_tables():
    schema_sql = """
    -- Day 2: Core Tables
    CREATE TABLE IF NOT EXISTS leads (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        phone VARCHAR(20) UNIQUE NOT NULL,
        age INT,
        income NUMERIC,
        credit_score INT,
        employment_type VARCHAR(50),
        status VARCHAR(50) DEFAULT 'pending',
        priority_score INT DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS calls (
        id SERIAL PRIMARY KEY,
        lead_id INT REFERENCES leads(id),
        call_sid VARCHAR(100) UNIQUE,
        start_time TIMESTAMP DEFAULT NOW(),
        end_time TIMESTAMP,
        duration INT,
        outcome VARCHAR(100)
    );

    CREATE TABLE IF NOT EXISTS applications (
        id SERIAL PRIMARY KEY,
        lead_id INT REFERENCES leads(id),
        call_id INT REFERENCES calls(id),
        consent_given BOOLEAN DEFAULT FALSE,
        card_recommended VARCHAR(100),
        status VARCHAR(50) DEFAULT 'initiated',
        extracted_data JSONB
    );

    -- Day 3: Extend Schema
    CREATE TABLE IF NOT EXISTS transcripts (
        id SERIAL PRIMARY KEY,
        call_id INT REFERENCES calls(id),
        speaker VARCHAR(20),
        text TEXT,
        timestamp TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS card_issuances (
        id SERIAL PRIMARY KEY,
        application_id INT REFERENCES applications(id),
        card_type VARCHAR(100),
        issued_at TIMESTAMP DEFAULT NOW(),
        status VARCHAR(50) DEFAULT 'processing'
    );

    CREATE TABLE IF NOT EXISTS audit_log (
        id SERIAL PRIMARY KEY,
        lead_id INT REFERENCES leads(id),
        old_status VARCHAR(50),
        new_status VARCHAR(50),
        changed_at TIMESTAMP DEFAULT NOW()
    );

    -- Indexes for fast lookups
    CREATE INDEX IF NOT EXISTS idx_leads_phone ON leads(phone);
    CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
    """
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(schema_sql)
            conn.commit()
    print("✅ Supabase schema initialized successfully.")

def test_connection():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                print("✅ Connected to DB:", cur.fetchone())
    except Exception as e:
        print("❌ Not connected:", e)

if __name__ == "__main__":
    test_connection()