# Sales Agent Conversation Graph Visualization
print("=" * 70)
print("📊 SALES AGENT CONVERSATION GRAPH STRUCTURE")
print("=" * 70)

print("""
FLOWCHART:
┌─────────────┐
│   START     │
│  (API Call) │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐
│   INTRO     │ ──► │VERIFY_INTEREST│
│             │     │              │
│ Agent says  │     │ Check if     │
│ hello &     │     │ interested   │
│ introduces  │     └──────┬───────┘
│ themselves │            │
└─────────────┘            │
                           ▼
                    ┌─────────────┐
                    │  END CALL  │
                    │ (Not       │
                    │  Interested)│
                    └─────────────┘
                           ▲
                           │
┌─────────────┐     ┌─────────────┐
│COLLECT_INFO │ ◄───┤VERIFY_INTEREST│
│            │     │              │
│ Ask for    │     └─────────────┘
│ income,    │            │
│ credit     │            ▼
│ score, etc │     ┌─────────────┐
└─────┬──────┘     │COLLECT_INFO │
      │            │            │
      │            │ Keep asking │
      │            │ until data  │
      │            │ complete    │
      └────────────┘
            │
            ▼
┌─────────────┐     ┌─────────────┐
│ RECOMMEND  │ ◄───┤COLLECT_INFO │
│            │     │            │
│ Show card  │     └─────────────┘
│ options &  │            │
│ benefits   │            ▼
└─────┬──────┘     ┌─────────────┐
      │            │ RECOMMEND  │
      │            │            │
      │            │ Agent      │
      │            │ recommends │
      │            │ best card  │
      └────────────┘
            │
            ▼
   ┌─────────────────┐
   │   OBJECTION     │ ◄─────────────────┐
   │                 │                   │
   │ Handle customer │                   │
   │ objections &    │                   │
   │ concerns        │                   │
   └────────┬────────┘                   │
            │                            │
            ▼                            │
   ┌─────────────────┐                   │
   │   RECOMMEND     │ ◄─────────────────┘
   │   (Again)       │
   │                 │
   │ Try different   │
   │ card or address │
   │ concerns        │
   └────────┬────────┘
            │
            ▼
┌─────────────┐     ┌─────────────┐
│  CONFIRM    │ ◄───┤ RECOMMEND  │
│             │     │            │
│ Get final   │     │            │
│ confirmation│     │            │
└─────┬───────┘     └─────────────┘
      │
      ▼
┌─────────────┐
│ SAVE_TO_DB  │
│             │
│ Save call   │
│ outcome &   │
│ lead status │
└─────┬───────┘
      │
      ▼
┌─────────────┐
│     END     │
│  (SUCCESS)  │
└─────────────┘
""")

print("\n" + "=" * 70)
print("📋 NODE DESCRIPTIONS:")
print("=" * 70)

nodes = {
    "intro": "Agent introduces themselves and starts the conversation",
    "verify_interest": "Checks if customer is interested in credit cards",
    "collect_info": "Gathers customer profile (income, credit score, spending habits)",
    "recommend": "Recommends the best matching credit card",
    "objection": "Handles customer objections and concerns",
    "confirm": "Gets final confirmation from customer",
    "save_to_db": "Saves call outcome and updates lead status"
}

for node, desc in nodes.items():
    print(f"🔹 {node.upper()}: {desc}")

print("\n" + "=" * 70)
print("🔀 CONDITIONAL ROUTES:")
print("=" * 70)

routes = [
    "verify_interest → collect_info (if interested) OR END (if not interested)",
    "collect_info → collect_info (if more data needed) OR recommend (if data complete)",
    "recommend → objection (if customer has concerns) OR confirm (if ready to proceed)",
    "objection → recommend (try different approach) OR END (give up)"
]

for route in routes:
    print(f"➡️  {route}")

print("\n" + "=" * 70)
print("💡 GRAPH CHARACTERISTICS:")
print("=" * 70)
print("• Entry Point: intro")
print("• Exit Points: END (success or failure)")
print("• State Management: Redis-backed session storage")
print("• Turn-based: One node per API call")
print("• Conditional Logic: Dynamic routing based on customer responses")
print("=" * 70)