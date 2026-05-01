"""
db/seed.py
Python seed script — alternative to seed.sql.
Useful if you want to run seeding from Python directly
without the psql command line.

Run:
  python db/seed.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from db.database import get_db, test_connection
from sqlalchemy import text

LEADS = [
    # (name, phone, age, income, credit_score, employment_type, city, state, language, status, priority_score)

    # High priority — salaried
    ("Rahul Sharma",    "9876543210", 28, 65000,  740, "salaried",      "Mumbai",     "Maharashtra",      "english", "pending", 95),
    ("Priya Patel",     "9845123456", 30, 72000,  760, "salaried",      "Bangalore",  "Karnataka",        "english", "pending", 93),
    ("Amit Verma",      "9812345678", 32, 80000,  750, "salaried",      "Delhi",      "Delhi",            "hindi",   "pending", 92),
    ("Sneha Nair",      "9723456789", 27, 58000,  720, "salaried",      "Chennai",    "Tamil Nadu",       "english", "pending", 90),
    ("Vikram Singh",    "9634567890", 35, 95000,  770, "salaried",      "Pune",       "Maharashtra",      "english", "pending", 90),
    ("Ananya Das",      "9745678901", 29, 62000,  730, "salaried",      "Kolkata",    "West Bengal",      "english", "pending", 88),
    ("Rohan Mehta",     "9856789012", 31, 75000,  755, "salaried",      "Hyderabad",  "Telangana",        "english", "pending", 88),
    ("Kavya Reddy",     "9967890123", 26, 55000,  715, "salaried",      "Bangalore",  "Karnataka",        "english", "pending", 85),
    ("Arjun Iyer",      "9078901234", 33, 88000,  765, "salaried",      "Chennai",    "Tamil Nadu",       "english", "pending", 85),
    ("Pooja Gupta",     "9189012345", 28, 48000,  700, "salaried",      "Jaipur",     "Rajasthan",        "hindi",   "pending", 82),

    # High priority — business
    ("Suresh Kumar",    "9290123456", 40, 120000, 780, "business",      "Mumbai",     "Maharashtra",      "hindi",   "pending", 95),
    ("Meena Agarwal",   "9301234567", 37, 100000, 760, "business",      "Delhi",      "Delhi",            "hindi",   "pending", 93),
    ("Rajesh Joshi",    "9412345678", 42, 90000,  750, "self_employed", "Pune",       "Maharashtra",      "hindi",   "pending", 88),
    ("Lakshmi Venkat",  "9523456789", 38, 85000,  745, "business",      "Hyderabad",  "Telangana",        "english", "pending", 87),
    ("Deepak Malhotra", "9634567891", 44, 110000, 775, "business",      "Chandigarh", "Punjab",           "hindi",   "pending", 87),

    # Medium priority
    ("Sanjay Bhatt",    "9078901235", 29, 38000,  690, "salaried",      "Ahmedabad",  "Gujarat",          "hindi",   "pending", 72),
    ("Ritu Sharma",     "9189012346", 25, 32000,  670, "salaried",      "Bhopal",     "Madhya Pradesh",   "hindi",   "pending", 70),
    ("Arun Nambiar",    "9290123457", 27, 42000,  695, "salaried",      "Kochi",      "Kerala",           "english", "pending", 70),
    ("Divya Saxena",    "9301234568", 30, 35000,  680, "salaried",      "Agra",       "Uttar Pradesh",    "hindi",   "pending", 68),
    ("Manoj Yadav",     "9412345679", 33, 45000,  700, "salaried",      "Patna",      "Bihar",            "hindi",   "pending", 68),
    ("Karan Kapoor",    "9078901236", 26, 35000,  665, "self_employed", "Mumbai",     "Maharashtra",      "english", "pending", 65),
    ("Tanvi Bose",      "9189012347", 28, 40000,  680, "self_employed", "Kolkata",    "West Bengal",      "english", "pending", 63),

    # Lower priority
    ("Mohan Lal",       "9523456791", 45, 22000,  640, "salaried",      "Meerut",     "Uttar Pradesh",    "hindi",   "pending", 45),
    ("Sarita Singh",    "9967890126", 35, 19000,  635, "salaried",      "Ranchi",     "Jharkhand",        "hindi",   "pending", 38),

    # Retry leads
    ("Ashok Meena",     "9078901237", 29, 55000,  710, "salaried",      "Jaipur",     "Rajasthan",        "hindi",   "retry",   75),
    ("Bhavna Shah",     "9189012348", 31, 62000,  725, "business",      "Surat",      "Gujarat",          "hindi",   "retry",   73),
    ("Chirag Patel",    "9290123459", 27, 48000,  695, "salaried",      "Vadodara",   "Gujarat",          "hindi",   "retry",   70),
]


INSERT_SQL = text("""
    INSERT INTO leads (
        name, phone, age, income, credit_score, employment_type,
        city, state, language, status, priority_score, source, created_at, updated_at
    ) VALUES (
        :name, :phone, :age, :income, :credit_score, :employment_type,
        :city, :state, :language, :status, :priority_score, 'seed_script', NOW(), NOW()
    )
    ON CONFLICT (phone) DO NOTHING
""")


def seed_leads():
    print("🌱 Seeding leads...")
    inserted = 0
    skipped  = 0

    with get_db() as db:
        for row in LEADS:
            try:
                db.execute(INSERT_SQL, {
                    "name":            row[0],
                    "phone":           row[1],
                    "age":             row[2],
                    "income":          row[3],
                    "credit_score":    row[4],
                    "employment_type": row[5],
                    "city":            row[6],
                    "state":           row[7],
                    "language":        row[8],
                    "status":          row[9],
                    "priority_score":  row[10],
                })
                inserted += 1
            except Exception as e:
                skipped += 1
                print(f"  ⚠️  Skipped {row[0]}: {e}")

    print(f"✅ Done — {inserted} leads inserted, {skipped} skipped (duplicates)")


def verify_seed():
    print("\n📊 Lead Summary:")
    with get_db() as db:
        # Count by status
        rows = db.execute(text("""
            SELECT status, COUNT(*) as total,
                   ROUND(AVG(income)) as avg_income,
                   ROUND(AVG(credit_score)) as avg_score
            FROM leads
            GROUP BY status ORDER BY total DESC
        """)).mappings().all()

        print(f"  {'Status':<20} {'Count':>6} {'Avg Income':>12} {'Avg Score':>10}")
        print("  " + "─" * 52)
        for r in rows:
            print(f"  {r['status']:<20} {r['total']:>6} {r['avg_income']:>12} {r['avg_score']:>10}")

        # Top 5 leads by priority
        top = db.execute(text("""
            SELECT name, phone, income, credit_score, priority_score, status
            FROM leads ORDER BY priority_score DESC LIMIT 5
        """)).mappings().all()

        print(f"\n🏆 Top 5 Leads (by priority):")
        for r in top:
            print(f"  {r['name']:<20} | ₹{r['income']:>8} | Score: {r['credit_score']} | Priority: {r['priority_score']} | {r['status']}")


def drop_all_data():
    """
    USE WITH CAUTION — wipes all data (keeps table structure).
    Only for development resets.
    """
    print("⚠️  Dropping all data...")
    with get_db() as db:
        db.execute(text("TRUNCATE leads, calls, applications, transcripts, card_issuances, audit_log, prompt_logs RESTART IDENTITY CASCADE"))
    print("✅ All tables cleared")


if __name__ == "__main__":
    print("🔌 Connecting to database...")
    if not test_connection():
        print("❌ Cannot connect to database. Check your DATABASE_URL in .env")
        sys.exit(1)

    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        drop_all_data()

    seed_leads()
    verify_seed()
