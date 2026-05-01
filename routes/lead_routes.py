"""
routes/lead_routes.py
Lead management endpoints.
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from db.db_utils import (
    get_all_leads, get_lead_by_id,
    insert_lead, update_lead_status
)

router = APIRouter(prefix="/leads", tags=["Leads"])
logger = logging.getLogger(__name__)


class CreateLeadRequest(BaseModel):
    name: str
    phone: str
    age: Optional[int] = None
    income: Optional[float] = None
    credit_score: Optional[int] = None
    employment_type: Optional[str] = None
    priority_score: Optional[int] = 50


class UpdateLeadStatusRequest(BaseModel):
    status: str   # pending | called | not_interested | applied | retry | unreachable


@router.get("/")
async def list_leads(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None
):
    """List all leads with optional status filter."""
    leads = get_all_leads(limit=limit, offset=offset, status=status)
    return {"leads": leads, "count": len(leads), "limit": limit, "offset": offset}


@router.get("/{lead_id}")
async def get_lead(lead_id: str):
    lead = get_lead_by_id(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.post("/")
async def create_lead(req: CreateLeadRequest):
    """Add a new lead to the database."""
    lead_id = insert_lead(req.dict())
    return {"lead_id": lead_id, "message": "Lead created successfully"}


@router.patch("/{lead_id}/status")
async def update_status(lead_id: str, req: UpdateLeadStatusRequest):
    valid_statuses = ["pending", "called", "not_interested", "applied", "retry", "unreachable"]
    if req.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    update_lead_status(lead_id, req.status)
    return {"lead_id": lead_id, "new_status": req.status}