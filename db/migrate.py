"""
db/migrate.py
Simple migration runner — runs schema.sql against your database.
Alembic is the proper way for production, but this is simpler for Phase 1/2.

Run:
  python db/migrate.py            # create tables
  python db/migrate.py --verify   # just verify tables exist
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from db.database import get_db, test_connection
from sqlalchemy import text


SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "schema.sql")

EXPECTED_TABLES = [
    "leads",
    "calls",
    "applications",
    "transcripts",
    "card_issuances",
    "audit_log",
    "prompt_logs",
]


def run_migration():
    """Read schema.sql and execute it entirely against the database."""
    print("📦 Running database migration...")

    if not os.path.exists(SCHEMA_FILE):
        print(f"❌ schema.sql not found at {SCHEMA_FILE}")
        sys.exit(1)

    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        sql = f.read()

    try:
        with get_db() as db:
            # Execute the entire script as a single transaction block
            db.execute(text(sql))
        print("✅ Migration done successfully!")
    except Exception as e:
        print(f"❌ Migration failed: {e}")


def verify_tables():
    """Check that all expected tables exist."""
    print("\n🔍 Verifying tables...")

    check_sql = text("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)

    with get_db() as db:
        rows = db.execute(check_sql).fetchall()
        existing = [r[0] for r in rows]

    all_good = True
    for table in EXPECTED_TABLES:
        if table in existing:
            print(f"  ✅ {table}")
        else:
            print(f"  ❌ {table} — MISSING")
            all_good = False

    if all_good:
        print("\n✅ All tables present. Database is ready!")
    else:
        print("\n❌ Some tables are missing. Check your schema.sql for errors.")
        sys.exit(1)


def show_table_counts():
    """Show row counts for all tables."""
    print("\n📊 Table row counts:")
    with get_db() as db:
        for table in EXPECTED_TABLES:
            try:
                count = db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                print(f"  {table:<25} {count:>8} rows")
            except Exception as e:
                print(f"  {table:<25} ERROR: {e}")


if __name__ == "__main__":
    print("🔌 Connecting to database...")
    if not test_connection():
        print("❌ Cannot connect. Check DATABASE_URL in your .env file")
        sys.exit(1)

    if "--verify" in sys.argv:
        verify_tables()
        show_table_counts()
    else:
        run_migration()
        verify_tables()
        show_table_counts()
        print("\n👉 Next step: run 'python db/seed.py' to insert dummy leads")