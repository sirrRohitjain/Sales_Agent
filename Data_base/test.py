import os
from dotenv import load_dotenv

load_dotenv()
print(os.getenv("SUPABASE_DB_URL"))