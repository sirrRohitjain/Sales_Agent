"""
tests/test_api.py
Integration tests for FastAPI endpoints.
Mocks DB and Redis so no real connections needed.

Run:
  pytest tests/test_api.py -v
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

MOCK_LEAD = {
    "id": "lead-test-001",
    "name": "Priya Patel",
    "phone": "9876543210",
    "age": 30,
    "income": 55000,
    "credit_score": 730,
    "employment_type": "salaried",
    "status": "pending",
    "priority_score": 90,
}

MOCK_INTRO_LLM = {
    "reply": "Hi Priya! Good morning, this is Riya calling from QuickBank. Do you have two minutes?",
    "extracted": {},
    "next_action": "continue"
}


class TestHealthEndpoint:
    @patch("db.database.test_connection", return_value=True)
    @patch("services.session_manager.test_redis", return_value=True)
    @patch("services.session_manager.get_active_call_count", return_value=0)
    @patch("db.db_utils.get_daily_stats", return_value={})
    def test_health_ok(self, *mocks):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


class TestStartCall:
    @patch("routes.call_routes.get_next_lead", return_value=MOCK_LEAD)
    @patch("routes.call_routes.lock_lead", return_value=True)
    @patch("routes.call_routes.create_call_record")
    @patch("graph.nodes.call_llm", return_value=MOCK_INTRO_LLM)
    @patch("routes.call_routes.save_state")
    @patch("routes.call_routes.save_transcript_chunk")
    def test_start_call_success(self, *mocks):
        resp = client.post("/call/start", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "call_id" in data
        assert "agent_reply" in data
        assert data["lead_name"] == "Priya Patel"
        assert len(data["agent_reply"]) > 0

    @patch("routes.call_routes.get_next_lead", return_value=None)
    def test_start_call_no_leads(self, mock_lead):
        resp = client.post("/call/start", json={})
        assert resp.status_code == 404

    @patch("routes.call_routes.get_lead_by_id", return_value=None)
    def test_start_call_invalid_lead_id(self, mock_lead):
        resp = client.post("/call/start", json={"lead_id": "nonexistent"})
        assert resp.status_code == 404

    @patch("routes.call_routes.get_next_lead", return_value=MOCK_LEAD)
    @patch("routes.call_routes.lock_lead", return_value=False)  # already locked
    def test_start_call_lead_already_locked(self, *mocks):
        resp = client.post("/call/start", json={})
        assert resp.status_code == 409


class TestRespondCall:
    def _make_session_state(self, call_id: str) -> dict:
        from graph.state import initial_state
        state = initial_state(call_id, MOCK_LEAD)
        state["messages"] = [
            {"role": "assistant", "content": "Hi Priya! Do you have two minutes?"}
        ]
        state["current_node"] = "intro"
        state["next_action"]  = "continue"
        return state

    @patch("routes.call_routes.get_state")
    @patch("routes.call_routes.save_transcript_chunk")
    @patch("routes.call_routes.save_state")
    @patch("routes.call_routes.refresh_ttl")
    @patch("graph.nodes.call_llm")
    def test_respond_success(self, mock_llm, mock_ttl, mock_save, mock_transcript, mock_get_state):
        call_id = "test-call-999"
        mock_get_state.return_value = self._make_session_state(call_id)
        mock_llm.return_value = {
            "reply": "Great! So is this about a credit card offer?",
            "extracted": {},
            "next_action": "continue"
        }

        resp = client.post("/call/respond", json={
            "call_id": call_id,
            "user_text": "Yes, I have a couple of minutes"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "agent_reply" in data
        assert len(data["agent_reply"]) > 0
        assert data["is_done"] is False

    @patch("routes.call_routes.get_state", return_value=None)
    def test_respond_session_not_found(self, mock_state):
        resp = client.post("/call/respond", json={
            "call_id": "nonexistent-call",
            "user_text": "Hello"
        })
        assert resp.status_code == 404

    @patch("routes.call_routes.get_state")
    def test_respond_empty_text_rejected(self, mock_get_state):
        mock_get_state.return_value = self._make_session_state("test-call-888")
        resp = client.post("/call/respond", json={
            "call_id": "test-call-888",
            "user_text": ""
        })
        assert resp.status_code == 400


class TestEndCall:
    @patch("routes.call_routes.get_state")
    @patch("routes.call_routes.delete_state")
    @patch("routes.call_routes.unlock_lead")
    @patch("routes.call_routes.update_call_outcome")
    @patch("routes.call_routes._save_partial_call")
    def test_end_call_success(self, mock_save, mock_outcome, mock_unlock, mock_delete, mock_state):
        call_id = "test-call-777"
        mock_state.return_value = {
            "call_id": call_id,
            "lead": MOCK_LEAD,
            "extracted_data": {"income": 50000},
            "current_node": "collect_info"
        }
        resp = client.post("/call/end", json={
            "call_id": call_id,
            "reason": "user_hangup"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["call_id"] == call_id


class TestLeadRoutes:
    @patch("routes.lead_routes.get_all_leads", return_value=[MOCK_LEAD])
    def test_list_leads(self, mock_leads):
        resp = client.get("/leads/")
        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    @patch("routes.lead_routes.get_lead_by_id", return_value=MOCK_LEAD)
    def test_get_lead_by_id(self, mock_lead):
        resp = client.get("/leads/lead-test-001")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Priya Patel"

    @patch("routes.lead_routes.get_lead_by_id", return_value=None)
    def test_get_lead_not_found(self, mock_lead):
        resp = client.get("/leads/nonexistent")
        assert resp.status_code == 404

    @patch("routes.lead_routes.insert_lead", return_value="new-lead-id-123")
    def test_create_lead(self, mock_insert):
        resp = client.post("/leads/", json={
            "name": "Ankit Gupta",
            "phone": "9123456789",
            "income": 45000,
            "employment_type": "salaried",
        })
        assert resp.status_code == 200
        assert resp.json()["lead_id"] == "new-lead-id-123"

    @patch("routes.lead_routes.update_lead_status")
    @patch("routes.lead_routes.get_lead_by_id", return_value=MOCK_LEAD)
    def test_update_lead_status(self, mock_get, mock_update):
        resp = client.patch("/leads/lead-test-001/status", json={"status": "called"})
        assert resp.status_code == 200

    def test_update_lead_invalid_status(self):
        resp = client.patch("/leads/lead-test-001/status", json={"status": "invalid_status"})
        assert resp.status_code == 400