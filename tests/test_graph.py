"""
tests/test_graph.py
Unit tests for LangGraph nodes and state transitions.
Uses mocked LLM calls so no real API key needed for testing.

Run:
  pytest tests/test_graph.py -v
"""

import pytest
from unittest.mock import patch, MagicMock
from graph.state import initial_state, AgentState
from graph.edges import (
    route_after_verify, route_after_collect,
    route_after_recommend, route_after_objection
)
from services.extractor import merge_extracted, is_collection_complete, _normalize_income
from services.card_recommender import recommend_card
from langgraph.graph import END


# ── Fixtures ───────────────────────────────────────────────────────

MOCK_LEAD = {
    "id": "test-lead-001",
    "name": "Rahul Sharma",
    "phone": "9876543210",
    "age": 28,
    "income": 50000,
    "credit_score": 720,
    "employment_type": "salaried",
    "status": "pending",
    "priority_score": 80,
}

MOCK_LLM_RESPONSE = {
    "reply": "Hi Rahul! Good morning, this is Priya from QuickBank.",
    "extracted": {},
    "next_action": "continue"
}


def make_state(overrides: dict = {}) -> AgentState:
    state = initial_state("test-call-001", MOCK_LEAD)
    state.update(overrides)
    return state


# ══════════════════════════════════════════════════════════════════
#  EXTRACTOR TESTS
# ══════════════════════════════════════════════════════════════════

class TestExtractor:
    def test_merge_keeps_existing_if_new_is_none(self):
        existing = {"income": 50000, "employment_type": "salaried"}
        new      = {"income": None, "spending_habits": "travel"}
        result   = merge_extracted(existing, new)
        assert result["income"] == 50000          # not overwritten
        assert result["spending_habits"] == "travel"  # new added

    def test_merge_updates_with_new_value(self):
        existing = {"income": 30000}
        new      = {"income": 50000}
        result   = merge_extracted(existing, new)
        assert result["income"] == 50000

    def test_merge_ignores_empty_strings(self):
        existing = {"employment_type": "salaried"}
        new      = {"employment_type": ""}
        result   = merge_extracted(existing, new)
        assert result["employment_type"] == "salaried"

    def test_is_collection_complete_true(self):
        data = {"income": 50000, "employment_type": "salaried", "spending_habits": "travel"}
        assert is_collection_complete(data) is True

    def test_is_collection_complete_false_missing_income(self):
        data = {"employment_type": "salaried"}
        assert is_collection_complete(data) is False

    def test_normalize_income_k_suffix(self):
        assert _normalize_income("50k") == 50000

    def test_normalize_income_with_comma(self):
        assert _normalize_income("50,000") == 50000

    def test_normalize_income_lakh(self):
        assert _normalize_income("1.5 lakh") == 150000

    def test_normalize_income_small_number(self):
        # "40" → assumes ₹40,000
        assert _normalize_income("40") == 40000


# ══════════════════════════════════════════════════════════════════
#  CARD RECOMMENDER TESTS
# ══════════════════════════════════════════════════════════════════

class TestCardRecommender:
    def test_platinum_card_for_traveler(self):
        profile = {"income": 100000, "credit_score": 760, "spending_habits": "travel flights"}
        card = recommend_card(profile)
        assert "Platinum" in card["name"]

    def test_gold_card_for_shopper(self):
        profile = {"income": 50000, "credit_score": 710, "spending_habits": "shopping dining"}
        card = recommend_card(profile)
        assert "Gold" in card["name"]

    def test_silver_card_for_low_income(self):
        profile = {"income": 20000, "credit_score": 660, "spending_habits": "groceries"}
        card = recommend_card(profile)
        assert "Silver" in card["name"]

    def test_default_card_when_very_low_income(self):
        profile = {"income": 5000, "credit_score": 600}
        card = recommend_card(profile)
        assert card is not None   # always returns something

    def test_card_has_required_keys(self):
        profile = {"income": 50000, "credit_score": 700}
        card = recommend_card(profile)
        assert "name" in card
        assert "benefits" in card
        assert "top_3_benefits" in card
        assert "fee" in card


# ══════════════════════════════════════════════════════════════════
#  EDGE / ROUTING TESTS
# ══════════════════════════════════════════════════════════════════

class TestEdges:
    def test_route_verify_not_interested_goes_to_end(self):
        state = make_state({"next_action": "not_interested"})
        result = route_after_verify(state)
        assert result == END

    def test_route_verify_continue_goes_to_collect(self):
        state = make_state({"next_action": "continue"})
        result = route_after_verify(state)
        assert result == "collect_info"

    def test_route_collect_goes_to_recommend_when_complete(self):
        state = make_state({
            "extracted_data": {"income": 50000, "employment_type": "salaried", "spending_habits": "shopping"},
            "turn_count": 2
        })
        result = route_after_collect(state)
        assert result == "recommend"

    def test_route_collect_stays_in_collect_when_incomplete(self):
        state = make_state({
            "extracted_data": {"income": 50000},  # missing employment
            "turn_count": 1
        })
        result = route_after_collect(state)
        assert result == "collect_info"

    def test_route_collect_goes_to_recommend_after_6_turns(self):
        # After 6 turns, we give up collecting and recommend anyway
        state = make_state({"extracted_data": {}, "turn_count": 7})
        result = route_after_collect(state)
        assert result == "recommend"

    def test_route_recommend_objection(self):
        state = make_state({"next_action": "objection"})
        result = route_after_recommend(state)
        assert result == "objection"

    def test_route_recommend_confirm(self):
        state = make_state({"next_action": "confirm"})
        result = route_after_recommend(state)
        assert result == "confirm"

    def test_route_objection_end_after_max(self):
        state = make_state({"next_action": "end", "objection_count": 3})
        result = route_after_objection(state)
        assert result == END

    def test_route_objection_retry_when_under_max(self):
        state = make_state({"next_action": "continue", "objection_count": 1})
        result = route_after_objection(state)
        assert result == "recommend"


# ══════════════════════════════════════════════════════════════════
#  NODE TESTS (with mocked LLM)
# ══════════════════════════════════════════════════════════════════

class TestNodes:
    @patch("graph.nodes.call_llm")
    def test_intro_node_adds_message(self, mock_llm):
        mock_llm.return_value = MOCK_LLM_RESPONSE
        from graph.nodes import intro_node
        state = make_state()
        result = intro_node(state)
        assert len(result["messages"]) == 1
        assert result["messages"][0]["role"] == "assistant"
        assert result["current_node"] == "intro"

    @patch("graph.nodes.call_llm")
    def test_verify_not_interested(self, mock_llm):
        mock_llm.return_value = {**MOCK_LLM_RESPONSE, "next_action": "not_interested"}
        from graph.nodes import verify_interest_node
        state = make_state({
            "messages": [
                {"role": "assistant", "content": "Hi Rahul!"},
                {"role": "user", "content": "I'm not interested"},
            ],
            "current_node": "intro"
        })
        result = verify_interest_node(state)
        assert result["next_action"] == "not_interested"

    @patch("graph.nodes.call_llm")
    def test_collect_info_extracts_data(self, mock_llm):
        mock_llm.return_value = {
            "reply": "Oh nice! And what do you do for work?",
            "extracted": {"income": 50000},
            "next_action": "continue"
        }
        from graph.nodes import collect_info_node
        state = make_state({
            "messages": [
                {"role": "assistant", "content": "What's your monthly income roughly?"},
                {"role": "user", "content": "About 50,000 a month"},
            ],
            "current_node": "verify_interest"
        })
        result = collect_info_node(state)
        assert result["extracted_data"].get("income") == 50000

    @patch("graph.nodes.call_llm")
    def test_confirm_sets_consent_true(self, mock_llm):
        mock_llm.return_value = {
            "reply": "Amazing! Our team will call you soon.",
            "extracted": {"consent_given": True},
            "next_action": "end"
        }
        from graph.nodes import confirm_node
        state = make_state({
            "messages": [
                {"role": "assistant", "content": "Shall I go ahead?"},
                {"role": "user", "content": "Yes, go ahead"},
            ],
            "card_recommended": "QuickBank Gold Rewards Card",
            "current_node": "recommend"
        })
        result = confirm_node(state)
        assert result["consent_given"] is True
        assert result["next_action"] == "end"

    @patch("graph.nodes.call_llm")
    def test_objection_count_increments(self, mock_llm):
        mock_llm.return_value = {
            "reply": "I totally understand! Actually the first year is free...",
            "extracted": {},
            "next_action": "continue"
        }
        from graph.nodes import objection_node
        state = make_state({
            "messages": [
                {"role": "user", "content": "The annual fee is too high"},
            ],
            "card_recommended": "QuickBank Gold Rewards Card",
            "objection_count": 0
        })
        result = objection_node(state)
        assert result["objection_count"] == 1


# ══════════════════════════════════════════════════════════════════
#  FULL CONVERSATION SIMULATION TEST
# ══════════════════════════════════════════════════════════════════

class TestFullFlow:
    @patch("graph.nodes.call_llm")
    def test_happy_path_state_transitions(self, mock_llm):
        """
        Simulate: interested customer → gives info → likes card → consents
        No real LLM or DB — everything mocked.
        """
        from graph.nodes import (
            intro_node, verify_interest_node, collect_info_node,
            recommend_node, confirm_node
        )
        from graph.edges import route_after_verify, route_after_collect, route_after_recommend
        from langgraph.graph import END

        state = make_state()

        # Turn 1: Intro
        mock_llm.return_value = {"reply": "Hi Rahul!", "extracted": {}, "next_action": "continue"}
        state = intro_node(state)
        assert state["current_node"] == "intro"

        # Turn 2: Customer says yes → verify
        state["messages"].append({"role": "user", "content": "Yes, I have 2 minutes"})
        mock_llm.return_value = {"reply": "Great!", "extracted": {}, "next_action": "continue"}
        state = verify_interest_node(state)
        assert route_after_verify(state) == "collect_info"

        # Turn 3-4: Collect info
        state["messages"].append({"role": "user", "content": "I earn about 60,000"})
        mock_llm.return_value = {
            "reply": "Got it!", "extracted": {"income": 60000}, "next_action": "continue"
        }
        state = collect_info_node(state)
        assert state["extracted_data"].get("income") == 60000

        state["messages"].append({"role": "user", "content": "I'm salaried in IT"})
        mock_llm.return_value = {
            "reply": "Perfect!", 
            "extracted": {"employment_type": "salaried", "spending_habits": "online shopping"},
            "next_action": "continue"
        }
        state = collect_info_node(state)
        assert route_after_collect(state) == "recommend"

        # Turn 5: Recommend
        mock_llm.return_value = {"reply": "The Gold card is perfect for you!", "extracted": {}, "next_action": "confirm"}
        state = recommend_node(state)
        assert state["card_recommended"] is not None
        assert route_after_recommend(state) == "confirm"

        # Turn 6: Confirm
        state["messages"].append({"role": "user", "content": "Yes, sounds good!"})
        mock_llm.return_value = {
            "reply": "Amazing!", "extracted": {"consent_given": True}, "next_action": "end"
        }
        state = confirm_node(state)
        assert state["consent_given"] is True
        assert state["next_action"] == "end"

        print("\n✅ Full happy path simulation passed!")