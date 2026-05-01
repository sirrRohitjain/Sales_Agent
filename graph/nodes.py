"""
graph/nodes.py
Every LangGraph node lives here.
Each node:
  1. Builds a prompt specific to its goal
  2. Calls the LLM
  3. Updates AgentState
  4. Returns updated state

PERSONA NOTE:
Priya sounds like a real Indian sales executive — warm, natural,
uses Hinglish phrases, reacts to what the customer says.
She never reveals she is AI and never uses robotic/corporate language.
"""

import logging
from datetime import datetime
from graph.state import AgentState
from services.llm_service import call_llm
from services.extractor import merge_extracted
from services.card_recommender import recommend_card_for_lead

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
#  SHARED PERSONA — injected into every node's system prompt
# ══════════════════════════════════════════════════════════════════

PERSONA = """
You are Priya, a sales executive at QuickBank India.
You are speaking to a potential customer on a phone call.

YOUR PERSONALITY & STYLE:
- Warm, confident, friendly — like a real person who genuinely wants to help
- Natural Indian English: use "actually", "basically", "you know", "right?", "na"
- Short sentences. React naturally. Show personality.
- Use emotional reactions: "Oh nice!", "I totally get that", "Hmm, that's fair"
- Reference what the customer said earlier in the conversation
- Never speak in bullet points or lists — this is a PHONE CALL
- One topic per response. Don't bombard them with too much at once.
- Keep replies under 3 sentences — real agents don't monologue

THINGS YOU MUST NEVER SAY:
- "I am an AI", "As an AI assistant", "I am a bot", "I am a virtual agent"
- "I have noted your response", "Please provide", "Could you please state"
- "I will now proceed to", "As per my records"
- Never use corporate/formal language

IF ASKED "Are you a real person?" or "Are you a human?" or "Are you a robot?":
→ Respond naturally: "Ha, I get that sometimes! I'm Priya, calling from QuickBank.
  Now let me not waste your time — I actually have something really useful for you."
→ Move on immediately. Do NOT confirm OR deny being AI.

LANGUAGE:
- If customer replies in Hindi → switch to Hinglish naturally
- If customer replies in English → stay in English
- Match their energy level (excited customer = be more enthusiastic)

RESPONSE FORMAT — STRICTLY JSON, NO MARKDOWN, NO EXTRA TEXT:
{
  "reply": "your natural conversational reply here",
  "extracted": {},
  "next_action": "continue | not_interested | objection | confirm | end"
}
"""


def _get_time_greeting() -> str:
    hour = datetime.now().hour
    if hour < 12:  return "Good morning"
    if hour < 17:  return "Good afternoon"
    return "Good evening"


def _first_name(lead: dict) -> str:
    return lead.get("name", "").split()[0] if lead.get("name") else "there"


def _last_user_msg(messages: list) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            return m.get("content", "")
    return ""


# ══════════════════════════════════════════════════════════════════
#  NODE 1 — INTRO
#  Goal: Warm opening. Ask if they have 2 minutes.
#  Does NOT mention credit card yet.
# ══════════════════════════════════════════════════════════════════

def intro_node(state: AgentState) -> AgentState:
    lead   = state["lead"]
    name   = _first_name(lead)
    greet  = _get_time_greeting()

    prompt = f"""{PERSONA}

YOUR TASK RIGHT NOW — Open the call:
Customer's first name: {name}
Time of day: {greet}

You just got connected. Do these things naturally in ONE short reply:
1. Confirm you're speaking with {name}
2. Introduce yourself as Priya from QuickBank
3. Say good {greet.split()[1]} / apologize for interrupting
4. Ask if they have "just two minutes" — real agents always do this first

Do NOT mention credit card yet. Just warm up and check if it's a good time.

Example style (don't copy word for word, vary it):
"Hi, is this {name}? Hi {name}! {greet}, this is Priya calling from QuickBank.
Hope I'm not catching you at a bad time — do you have just two minutes? 
I have something that I think will be really useful for you."

next_action: always "continue" here."""

    result = call_llm(prompt, [])

    state["messages"].append({"role": "assistant", "content": result["reply"]})
    state["current_node"] = "intro"
    state["next_action"]  = "continue"
    logger.info(f"[{state['call_id']}] intro_node done")
    return state


# ══════════════════════════════════════════════════════════════════
#  NODE 2 — VERIFY INTEREST
#  Goal: Understand if customer wants to continue or wants to end.
# ══════════════════════════════════════════════════════════════════

def verify_interest_node(state: AgentState) -> AgentState:
    user_reply = _last_user_msg(state["messages"])
    name       = _first_name(state["lead"])

    prompt = f"""{PERSONA}

YOUR TASK — Only check if the customer wants to hear the offer.
Customer said: "{user_reply}"

DO NOT ask any questions about their lifestyle, spending, income, or habits.
Just gauge their interest from what they said.

If interested (yes / okay / sure / haan / tell me):
  → Say something like "Great! So we have a really good credit card offer 
    for you — let me tell you about it"
  → next_action: "continue"

If not interested / busy:
  → Apologize warmly, wish them a good day
  → next_action: "not_interested"

If unclear:
  → Try once more: "It'll be just a minute, I think you'll like this one"
  → next_action: "continue"

No questions. Just react to what they said and move forward."""

    result = call_llm(prompt, state["messages"])
    state["messages"].append({"role": "assistant", "content": result["reply"]})
    state["next_action"]  = result.get("next_action", "continue")
    state["current_node"] = "verify_interest"
    return state






# ══════════════════════════════════════════════════════════════════
#  NODE 4 — RECOMMEND CARD
#  Goal: Present the best card in a natural, exciting way.
#  Connect benefits to the customer's specific profile.
# ══════════════════════════════════════════════════════════════════

def recommend_node(state: AgentState) -> AgentState:
    from services.card_recommender import recommend_card_for_lead

    lead = state["lead"]
    name = _first_name(lead)

    # One line — fetches from DB internally
    card = recommend_card_for_lead(str(lead["id"]))
    state["card_recommended"] = card["name"]

    prompt = f"""{PERSONA}

YOUR TASK — Present the card offer confidently.
Customer: {name}
Card: {card['name']}
Fee: {card['fee']}
Top benefits: {card['top_3_benefits']}

Keep it natural and brief — 2-3 sentences max.
Don't mention anything about their income or records.
Just say "we have a great offer for you".
End with "Sounds good?" or "Want me to go ahead?"

next_action: "confirm" if positive, "objection" if concern raised."""

    result = call_llm(prompt, state["messages"])
    state["messages"].append({"role": "assistant", "content": result["reply"]})
    state["next_action"]  = result.get("next_action", "confirm")
    state["current_node"] = "recommend"
    return state
# ══════════════════════════════════════════════════════════════════
#  NODE 5 — HANDLE OBJECTION
#  Goal: Address concern naturally, not defensively.
#  Max 3 objections then gracefully close.
# ══════════════════════════════════════════════════════════════════

def objection_node(state: AgentState) -> AgentState:
    state["objection_count"] += 1
    objection = _last_user_msg(state["messages"])
    card      = state["card_recommended"]
    name      = _first_name(state["lead"])
    count     = state["objection_count"]

    prompt = f"""{PERSONA}

YOUR TASK — Handle this objection naturally and warmly.
Customer said: "{objection}"
Card: {card}
This is objection #{count} (max 3 before we end gracefully)

COMMON OBJECTIONS AND NATURAL RESPONSES:
- "Annual fee / charges": 
  "Totally fair concern! So actually the first year is completely free — 
   zero fee. And after that, the rewards you earn through the year 
   easily cover the fee. Most of our customers actually end up in profit."

- "I already have a card / I have too many cards":
  "Ha, that's actually the most common thing I hear! But here's the thing — 
   most people use this as a secondary card specifically for [their spending habit]. 
   Like a lot of my customers use it just for [specific benefit] and it makes 
   a huge difference."

- "I'll think about it / let me check":
  "Of course, no pressure at all! But I should mention — the waived joining fee 
   and the bonus points I'm offering? That's only valid this month. 
   I'd hate for you to miss it. Is there something specific holding you back?"

- "Not interested / don't need it":
  "That's completely okay {name}! Can I ask though — is it more that you're 
   happy with what you have, or is it more the timing? Sometimes people 
   just need a different kind of card."

- "No time / busy":
  "Absolutely, I'll be super quick — literally 30 more seconds. 
   The one thing I want you to know is [most relevant benefit]. 
   Our team can call you back to finish the paperwork at your convenience."

{"If objection count >= 3: Say goodbye gracefully. Thank them for their time. Be warm. next_action: 'end'" if count >= 3 else "Try to address the objection and bring them back to the card. next_action: 'continue'"}"""

    result = call_llm(prompt, state["messages"])

    state["messages"].append({"role": "assistant", "content": result["reply"]})
    state["next_action"]  = result.get("next_action", "continue")
    state["current_node"] = "objection"
    logger.info(f"[{state['call_id']}] objection_node #{count} | action: {state['next_action']}")
    return state


# ══════════════════════════════════════════════════════════════════
#  NODE 6 — CONFIRM & GET CONSENT
#  Goal: Get final yes. Explain next steps (KYC call).
#  Sound excited but not pushy.
# ══════════════════════════════════════════════════════════════════

def confirm_node(state: AgentState) -> AgentState:
    card  = state["card_recommended"]
    name  = _first_name(state["lead"])

    prompt = f"""{PERSONA}

YOUR TASK — Close the deal naturally and warmly.
Customer: {name}
Card: {card}

WHAT TO DO:
- Confirm they want to proceed with the {card}
- Explain next steps casually (NOT like legal terms):
  "Our team will give you a quick call in the next day or two — 
   they'll just need your PAN card and Aadhaar details to complete the KYC. 
   The whole thing takes like 5 minutes."
- Get their verbal confirmation that it's okay

IF THEY SAY YES:
"Amazing {name}! I've noted everything. You'll get an SMS confirmation on this 
number shortly. Our team will call you within 24-48 hours for the KYC. 
It was so nice speaking with you — have a great rest of your day!"
extracted: {{"consent_given": true}}
next_action: "end"

IF THEY BACK OUT / HESITATE:
"No worries at all {name}! If you change your mind, you can always 
call us at 1800-XXX-XXXX. Hope you have a great day!"
extracted: {{"consent_given": false}}
next_action: "end"

React to what they say. If they have a last-minute concern, address it briefly."""

    result = call_llm(prompt, state["messages"])

    state["messages"].append({"role": "assistant", "content": result["reply"]})
    extracted = result.get("extracted", {})
    state["extracted_data"] = merge_extracted(state["extracted_data"], extracted)
    state["consent_given"]  = extracted.get("consent_given", False)
    state["next_action"]    = "end"
    state["current_node"]   = "confirm"
    logger.info(f"[{state['call_id']}] confirm_node | consent: {state['consent_given']}")
    return state


# ══════════════════════════════════════════════════════════════════
#  NODE 7 — SAVE TO DATABASE
#  Goal: Persist everything to PostgreSQL, trigger async tasks.
#  This is a non-conversational node — no LLM call here.
# ══════════════════════════════════════════════════════════════════

def save_to_db_node(state: AgentState) -> AgentState:
    from db.db_utils import save_application, update_lead_status, update_call_outcome, log_audit_event

    try:
        # Save application record
        app_id = save_application(state)

        # Update lead status
        if state["consent_given"]:
            update_lead_status(state["lead"]["id"], "applied")
            # Trigger async card processing
            try:
                from tasks.celery_tasks import process_application
                process_application.delay(app_id, state["call_id"])
                logger.info(f"Celery task queued for application {app_id}")
            except Exception as e:
                logger.error(f"Celery task failed to queue: {e}")
        else:
            update_lead_status(state["lead"]["id"], "not_interested")

        # Update call record
        update_call_outcome(state["call_id"], "completed")

        # Audit log
        log_audit_event(
            entity_type="call",
            entity_id=state["call_id"],
            action="call_completed",
            details={
                "consent_given": state["consent_given"],
                "card_recommended": state["card_recommended"],
                "turn_count": state["turn_count"],
            }
        )

        state["current_node"] = "saved"
        logger.info(f"[{state['call_id']}] save_to_db_node complete | app_id: {app_id}")

    except Exception as e:
        logger.error(f"[{state['call_id']}] save_to_db_node failed: {e}")
        state["error"] = str(e)

    return state