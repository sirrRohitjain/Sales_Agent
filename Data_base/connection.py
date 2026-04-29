import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    """Returns a new psycopg v3 connection to Supabase."""
    return psycopg.connect(os.getenv("SUPABASE_DB_URL"))

# Upstash REST credentials
UPSTASH_URL = os.getenv("UPSTASH_REDIS_REST_URL")
UPSTASH_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")
UPSTASH_HEADERS = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}