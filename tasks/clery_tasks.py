"""
tasks/celery_tasks.py
Async background tasks using Celery + Redis broker.

Tasks:
  process_application  — eligibility check + card issuance after consent
  schedule_retry_call  — queue a retry for unreachable leads
  send_sms_confirmation — send confirmation SMS (stub for Phase 4)

Start worker:
  celery -A tasks.celery_tasks worker --loglevel=info

Monitor:
  celery -A tasks.celery_tasks flower
"""

import os
import logging
from celery import Celery
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

BROKER_URL  = os.getenv("CELERY_BROKER_URL",  "redis://localhost:6379/1")
BACKEND_URL = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

celery_app = Celery(
    "credit_agent",
    broker=BROKER_URL,
    backend=BACKEND_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
    task_acks_late=True,            # only ack after task completes
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,   # one task at a time per worker
    task_routes={
        "tasks.celery_tasks.process_application": {"queue": "applications"},
        "tasks.celery_tasks.schedule_retry_call":  {"queue": "retries"},
    }
)


# ══════════════════════════════════════════════════════════════════
#  TASK 1 — PROCESS APPLICATION
#  Runs after customer gives consent.
#  Checks eligibility → creates card issuance record.
# ══════════════════════════════════════════════════════════════════

@celery_app.task(
    bind=True,
    name="tasks.celery_tasks.process_application",
    max_retries=3,
    default_retry_delay=60,    # retry after 60 seconds on failure
)
def process_application(self, application_id: str, call_id: str):
    """
    Background task triggered after customer consent.
    1. Fetch application from DB
    2. Run eligibility check
    3. Create card issuance record
    4. Send SMS confirmation
    """
    from db.db_utils import (
        get_application_by_call, update_application_status,
        create_card_issuance, update_card_issuance_status, log_audit_event
    )

    logger.info(f"Processing application: {application_id} | call: {call_id}")

    try:
        # Fetch application
        application = get_application_by_call(call_id)
        if not application:
            logger.error(f"Application not found for call {call_id}")
            return {"status": "error", "reason": "application_not_found"}

        # ── Eligibility check ──────────────────────────────────────
        eligible, reason = check_eligibility(application)

        if eligible:
            # Create card issuance record
            issuance_id = create_card_issuance(
                application_id=str(application["id"]),
                card_type=application.get("card_recommended", "QuickBank Silver Cashback Card")
            )

            # Simulate bank API call (Phase 4 will replace this with real API)
            update_card_issuance_status(issuance_id, "pending", reference=f"QB{issuance_id[:8].upper()}")
            update_application_status(str(application["id"]), "pending_kyc")

            log_audit_event("application", str(application["id"]), "processing_started", {
                "issuance_id": issuance_id,
                "card_type": application.get("card_recommended"),
            })

            # Send SMS (stub — Phase 4)
            send_sms_confirmation.delay(
                phone=application.get("lead_id"),   # will be resolved in Phase 4
                message=f"Your credit card application is received! Reference: QB{issuance_id[:8].upper()}. Our team will call within 48 hours for KYC."
            )

            logger.info(f"✅ Application {application_id} approved, issuance started")
            return {"status": "success", "issuance_id": issuance_id}

        else:
            update_application_status(str(application["id"]), "rejected")
            log_audit_event("application", str(application["id"]), "rejected", {"reason": reason})
            logger.warning(f"Application {application_id} rejected: {reason}")
            return {"status": "rejected", "reason": reason}

    except Exception as exc:
        logger.error(f"process_application failed: {exc}")
        raise self.retry(exc=exc)


# ══════════════════════════════════════════════════════════════════
#  TASK 2 — RETRY CALL
#  Schedule a retry for leads that didn't pick up.
# ══════════════════════════════════════════════════════════════════

@celery_app.task(
    name="tasks.celery_tasks.schedule_retry_call",
    max_retries=1,
)
def schedule_retry_call(lead_id: str, attempt: int = 1):
    """
    Called when a lead didn't pick up.
    Updates status to 'retry' and can trigger next call.
    """
    from db.db_utils import update_lead_status
    MAX_ATTEMPTS = 3

    if attempt >= MAX_ATTEMPTS:
        update_lead_status(lead_id, "unreachable")
        logger.info(f"Lead {lead_id} marked unreachable after {attempt} attempts")
    else:
        update_lead_status(lead_id, "retry")
        logger.info(f"Lead {lead_id} scheduled for retry (attempt {attempt + 1})")


# ══════════════════════════════════════════════════════════════════
#  TASK 3 — SEND SMS (stub for Phase 4)
# ══════════════════════════════════════════════════════════════════

@celery_app.task(
    name="tasks.celery_tasks.send_sms_confirmation",
    max_retries=3,
    default_retry_delay=30,
)
def send_sms_confirmation(phone: str, message: str):
    """
    Send SMS via Twilio (Phase 4 will add real Twilio code here).
    Currently just logs the message.
    """
    logger.info(f"📱 SMS to {phone}: {message}")
    # Phase 4: 
    # from twilio.rest import Client
    # client = Client(TWILIO_SID, TWILIO_AUTH)
    # client.messages.create(to=phone, from_=TWILIO_NUMBER, body=message)
    return {"status": "sent", "phone": phone}


# ══════════════════════════════════════════════════════════════════
#  ELIGIBILITY ENGINE (simple rule-based, Phase 4 will add CIBIL)
# ══════════════════════════════════════════════════════════════════

def check_eligibility(application: dict) -> tuple[bool, str]:
    """
    Basic eligibility rules.
    Returns (is_eligible: bool, reason: str)

    Phase 4 will replace this with actual CIBIL bureau API call.
    """
    income = application.get("income_stated") or 0
    try:
        income = float(str(income).replace(",", ""))
    except (ValueError, TypeError):
        income = 0

    if income < 10000:
        return False, "income_below_minimum"

    employment = str(application.get("employment_type", "")).lower()
    if employment in ["unemployed", "student"] and income < 15000:
        return False, "student_income_insufficient"

    return True, "eligible"