from Data_base.connection import get_db_connection

def get_pending_leads(limit: int = 10):
    query = """
        SELECT id, name, phone, age, income, credit_score, priority_score 
        FROM leads 
        WHERE status = 'pending' 
        ORDER BY priority_score DESC 
        LIMIT %s
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (limit,))
            columns = [desc[0] for desc in cur.description]
            # Convert tuples to list of dicts for easy API usage
            return [dict(zip(columns, row)) for row in cur.fetchall()]

def update_lead_status(lead_id: int, new_status: str):
    query = """
        UPDATE leads SET status = %s WHERE id = %s RETURNING status;
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (new_status, lead_id))
            conn.commit()
            return cur.fetchone()
    
print(get_pending_leads())    
