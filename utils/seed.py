import random
from faker import Faker
from Data_base.connection import get_db_connection

fake = Faker('en_IN')

def seed_leads(num: int = 10):
    employments = ["Salaried", "Self-employed", "Business", "Student"]
    
    query = """
        INSERT INTO leads (name, phone, age, income, credit_score, employment_type, status, priority_score)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            print(f"Inserting {num} records into Supabase...")
            for _ in range(num):
                cur.execute(query, (
                    fake.name(),
                    fake.phone_number()[:15],
                    random.randint(21, 60),
                    random.randint(300000, 2500000),
                    random.randint(600, 850),
                    random.choice(employments),
                    "pending",
                    random.randint(1, 100)
                ))
            conn.commit()
    print("✅ Seeding complete!")

if __name__ == "__main__":
    seed_leads()