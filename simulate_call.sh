#!/bin/bash
# simulate_call.sh
# Simulates a full 8-turn conversation via curl.
# Run: chmod +x simulate_call.sh && ./simulate_call.sh
# Make sure your FastAPI server is running: uvicorn main:app --reload

BASE_URL="http://localhost:8000"
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Credit Card Sales Agent — Call Simulation     ${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════${NC}\n"

# ── Step 1: Start the call ─────────────────────────────────────────
echo -e "${GREEN}[1] Starting call...${NC}"
START_RESP=$(curl -s -X POST "$BASE_URL/call/start" \
  -H "Content-Type: application/json" \
  -d '{}')

echo "Response: $START_RESP"
CALL_ID=$(echo $START_RESP | python3 -c "import sys, json; print(json.load(sys.stdin)['call_id'])")
AGENT_REPLY=$(echo $START_RESP | python3 -c "import sys, json; print(json.load(sys.stdin)['agent_reply'])")
echo -e "\n📞 Call ID: $CALL_ID"
echo -e "🤖 Agent: $AGENT_REPLY\n"

# ── Helper function ────────────────────────────────────────────────
send_response() {
    USER_TEXT="$1"
    echo -e "👤 Customer: $USER_TEXT"
    
    RESP=$(curl -s -X POST "$BASE_URL/call/respond" \
      -H "Content-Type: application/json" \
      -d "{\"call_id\": \"$CALL_ID\", \"user_text\": \"$USER_TEXT\"}")
    
    AGENT_REPLY=$(echo $RESP | python3 -c "import sys, json; d=json.load(sys.stdin); print(d['agent_reply'])")
    IS_DONE=$(echo $RESP | python3 -c "import sys, json; d=json.load(sys.stdin); print(d['is_done'])")
    NODE=$(echo $RESP | python3 -c "import sys, json; d=json.load(sys.stdin); print(d['current_node'])")
    
    echo -e "🤖 Agent: $AGENT_REPLY"
    echo -e "   [node: $NODE | done: $IS_DONE]\n"
    
    if [ "$IS_DONE" = "True" ]; then
        echo -e "${GREEN}✅ Call completed!${NC}"
        exit 0
    fi
    
    sleep 1  # Small delay between turns
}

# ── Conversation turns ─────────────────────────────────────────────
send_response "Yes, I have a couple of minutes"
send_response "I'm working at an IT company, salaried"
send_response "Around 55,000 per month"
send_response "Mostly shopping online and dining out"
send_response "Sounds interesting, tell me more"
send_response "What about the annual fee?"  # objection
send_response "Okay, that makes sense. I'm interested"
send_response "Yes, go ahead with the application"

# ── Final state ────────────────────────────────────────────────────
echo -e "\n${GREEN}── Final Call State ──${NC}"
curl -s "$BASE_URL/call/$CALL_ID/state" | python3 -m json.tool

echo -e "\n${GREEN}── Transcript ──${NC}"
curl -s "$BASE_URL/call/$CALL_ID/transcript" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for m in data.get('transcript', []):
    speaker = m.get('speaker', m.get('role', '?'))
    content = m.get('content', m.get('text', ''))
    print(f'{speaker.upper()}: {content}')
    print()
"