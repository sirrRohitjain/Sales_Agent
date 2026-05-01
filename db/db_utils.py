"""
db/db_utils.py
All database CRUD operations.
Every function uses the get_db() context manager.
"""

import uuid
import json
import logging
from datetime import datetime
from sqlalchemy import text
from db.database import get_db

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
#  LEADS
# ══════════════════════════════════════════════════════════════════

def get_next_lead() -> dict | None:
    """
    Pick the highest priority pending lead that is not currently locked.
    Called by the call scheduler to decide who to call next.
    """
    query = text("""
        SELECT id, name, phone, age, income, credit_score,
               employment_type, status, priority_score
        FROM leads
        WHERE status = 'pending'
          AND id NOT IN (
              SELECT lead_id FROM calls
              WHERE outcome IS NULL  -- currently active call
          )
        ORDER BY priority_score DESC, created_at ASC
        LIMIT 1
    """)
    with get_db() as db:
        row = db.execute(query).mappings().first()
        return dict(row) if row else None


def get_lead_by_id(lead_id: str) -> dict | None:
    query = text("SELECT * FROM leads WHERE id = :id")
    with get_db() as db:
        row = db.execute(query, {"id": lead_id}).mappings().first()
        return dict(row) if row else None


def get_lead_by_phone(phone: str) -> dict | None:
    query = text("SELECT * FROM leads WHERE phone = :phone")
    with get_db() as db:
        row = db.execute(query, {"phone": phone}).mappings().first()
        return dict(row) if row else None


def update_lead_status(lead_id: str, status: str):
    """
    Status values: pending | called | not_interested | applied | retry | unreachable
    """
    query = text("""
        UPDATE leads SET status = :status, updated_at = NOW()
        WHERE id = :id
    """)
    with get_db() as db:
        db.execute(query, {"id": lead_id, "status": status})
    logger.info(f"Lead {lead_id} status → {status}")


def get_all_leads(limit: int = 50, offset: int = 0, status: str = None) -> list[dict]:
    if status:
        query = text("""
            SELECT * FROM leads WHERE status = :status
            ORDER BY priority_score DESC LIMIT :limit OFFSET :offset
        """)
        params = {"status": status, "limit": limit, "offset": offset}
    else:
        query = text("SELECT * FROM leads ORDER BY priority_score DESC LIMIT :limit OFFSET :offset")
        params = {"limit": limit, "offset": offset}

    with get_db() as db:
        rows = db.execute(query, params).mappings().all()
        return [dict(r) for r in rows]


def insert_lead(data: dict) -> str:
    lead_id = str(uuid.uuid4())
    query = text("""
        INSERT INTO leads (id, name, phone, age, income, credit_score,
                           employment_type, status, priority_score, created_at)
        VALUES (:id, :name, :phone, :age, :income, :credit_score,
                :employment_type, 'pending', :priority_score, NOW())
    """)
    with get_db() as db:
        db.execute(query, {
            "id": lead_id,
            "name": data["name"],
            "phone": data["phone"],
            "age": data.get("age"),
            "income": data.get("income"),
            "credit_score": data.get("credit_score"),
            "employment_type": data.get("employment_type"),
            "priority_score": data.get("priority_score", 50),
        })
    return lead_id


# ══════════════════════════════════════════════════════════════════
#  CALLS
# ══════════════════════════════════════════════════════════════════

def create_call_record(call_id: str, lead_id: str) -> str:
    query = text("""
        INSERT INTO calls (id, lead_id, start_time, outcome, created_at)
        VALUES (:id, :lead_id, NOW(), NULL, NOW())
    """)
    with get_db() as db:
        db.execute(query, {"id": call_id, "lead_id": lead_id})
    logger.info(f"Call record created: {call_id}")
    return call_id


def update_call_outcome(call_id: str, outcome: str, duration_seconds: int = 0):
    """
    outcome: connected | not_answered | busy | failed | completed
    """
    query = text("""
        UPDATE calls
        SET outcome = :outcome,
            end_time = NOW(),
            duration_seconds = :duration,
            updated_at = NOW()
        WHERE id = :id
    """)
    with get_db() as db:
        db.execute(query, {
            "id": call_id,
            "outcome": outcome,
            "duration": duration_seconds
        })


def get_call_by_id(call_id: str) -> dict | None:
    query = text("SELECT * FROM calls WHERE id = :id")
    with get_db() as db:
        row = db.execute(query, {"id": call_id}).mappings().first()
        return dict(row) if row else None


# ══════════════════════════════════════════════════════════════════
#  APPLICATIONS
# ══════════════════════════════════════════════════════════════════

def save_application(state: dict) -> str:
    """
    Called from save_to_db_node in LangGraph.
    Saves the complete application after call ends.
    """
    app_id = str(uuid.uuid4())
    extracted = state.get("extracted_data", {})
    transcript = state.get("messages", [])

    query = text("""
        INSERT INTO applications (
            id, lead_id, call_id, income_stated, employment_type,
            existing_cards, spending_habits, card_recommended,
            consent_given, status, extracted_data, transcript,
            objection_count, turn_count, created_at
        ) VALUES (
            :id, :lead_id, :call_id, :income, :employment,
            :existing_cards, :spending_habits, :card_recommended,
            :consent, :status, :extracted_data, :transcript,
            :objection_count, :turn_count, NOW()
        )
    """)

    status = "applied" if state.get("consent_given") else "not_converted"

    with get_db() as db:
        db.execute(query, {
            "id": app_id,
            "lead_id": state["lead"]["id"],
            "call_id": state["call_id"],
            "income": extracted.get("income"),
            "employment": extracted.get("employment_type"),
            "existing_cards": extracted.get("existing_cards"),
            "spending_habits": extracted.get("spending_habits"),
            "card_recommended": state.get("card_recommended"),
            "consent": state.get("consent_given", False),
            "status": status,
            "extracted_data": json.dumps(extracted),
            "transcript": json.dumps(transcript),
            "objection_count": state.get("objection_count", 0),
            "turn_count": state.get("turn_count", 0),
        })

    logger.info(f"Application saved: {app_id} | status: {status}")
    return app_id


def get_application_by_call(call_id: str) -> dict | None:
    query = text("SELECT * FROM applications WHERE call_id = :call_id")
    with get_db() as db:
        row = db.execute(query, {"call_id": call_id}).mappings().first()
        return dict(row) if row else None


def update_application_status(app_id: str, status: str):
    """status: applied | approved | rejected | pending_kyc"""
    query = text("""
        UPDATE applications SET status = :status, updated_at = NOW()
        WHERE id = :id
    """)
    with get_db() as db:
        db.execute(query, {"id": app_id, "status": status})


# ══════════════════════════════════════════════════════════════════
#  TRANSCRIPTS
# ══════════════════════════════════════════════════════════════════

def save_transcript_chunk(call_id: str, speaker: str, text_content: str):
    """Save individual transcript lines during the call (real-time)."""
    query = text("""
        INSERT INTO transcripts (id, call_id, speaker, content, created_at)
        VALUES (:id, :call_id, :speaker, :content, NOW())
    """)
    with get_db() as db:
        db.execute(query, {
            "id": str(uuid.uuid4()),
            "call_id": call_id,
            "speaker": speaker,
            "content": text_content,
        })


def get_full_transcript(call_id: str) -> list[dict]:
    query = text("""
        SELECT speaker, content, created_at
        FROM transcripts WHERE call_id = :call_id
        ORDER BY created_at ASC
    """)
    with get_db() as db:
        rows = db.execute(query, {"call_id": call_id}).mappings().all()
        return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════
#  CARD ISSUANCES
# ══════════════════════════════════════════════════════════════════

def create_card_issuance(application_id: str, card_type: str) -> str:
    issuance_id = str(uuid.uuid4())
    query = text("""
        INSERT INTO card_issuances (id, application_id, card_type, status, created_at)
        VALUES (:id, :app_id, :card_type, 'pending', NOW())
    """)
    with get_db() as db:
        db.execute(query, {
            "id": issuance_id,
            "app_id": application_id,
            "card_type": card_type,
        })
    return issuance_id


def update_card_issuance_status(issuance_id: str, status: str, reference: str = None):
    """status: pending | issued | rejected"""
    query = text("""
        UPDATE card_issuances
        SET status = :status, bank_reference = :reference, updated_at = NOW()
        WHERE id = :id
    """)
    with get_db() as db:
        db.execute(query, {"id": issuance_id, "status": status, "reference": reference})


# ══════════════════════════════════════════════════════════════════
#  AUDIT LOG
# ══════════════════════════════════════════════════════════════════

def log_audit_event(entity_type: str, entity_id: str, action: str, details: dict = None):
    query = text("""
        INSERT INTO audit_log (id, entity_type, entity_id, action, details, created_at)
        VALUES (:id, :entity_type, :entity_id, :action, :details, NOW())
    """)
    with get_db() as db:
        db.execute(query, {
            "id": str(uuid.uuid4()),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": action,
            "details": json.dumps(details or {}),
        })


# ══════════════════════════════════════════════════════════════════
#  ANALYTICS
# ══════════════════════════════════════════════════════════════════

def get_daily_stats() -> dict:
    query = text("""
        SELECT
            COUNT(DISTINCT c.id)                                    AS total_calls,
            COUNT(DISTINCT CASE WHEN c.outcome='completed' THEN c.id END) AS connected,
            COUNT(DISTINCT CASE WHEN a.consent_given=true THEN a.id END)  AS converted,
            COUNT(DISTINCT CASE WHEN ci.status='issued' THEN ci.id END)   AS cards_issued
        FROM calls c
        LEFT JOIN applications a ON a.call_id = c.id
        LEFT JOIN card_issuances ci ON ci.application_id = a.id
        WHERE c.created_at >= CURRENT_DATE
    """)
    with get_db() as db:
        row = db.execute(query).mappings().first()
        return dict(row) if row else {}