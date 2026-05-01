# Sales Agent Conversation Graph - Simplified Flow
print("=" * 60)
print("🔄 SALES AGENT CONVERSATION FLOW")
print("=" * 60)

print("""
CALL START → INTRO → VERIFY_INTEREST →─┬─→ END (Not interested)
                                       │
                                       ▼
COLLECT_INFO ←─────────────────────────┘
     ▲
     │ (Loop until data complete)
     ▼
RECOMMEND ←─────────────────────────────┐
     │                                   │
     ├─→ OBJECTION →─┬─→ RECOMMEND ─────┘
     │               │
     │               └─→ END (Give up)
     │
     ▼
 CONFIRM → SAVE_TO_DB → END (Success)
""")

print("\n" + "=" * 60)
print("📝 DETAILED FLOW EXPLANATION:")
print("=" * 60)

flow_steps = [
    "1. START: API call initiates conversation",
    "2. INTRO: Agent says hello and introduces themselves",
    "3. VERIFY_INTEREST: Ask if customer wants credit card info",
    "   ├── If NO → END (Call ends politely)",
    "   └── If YES → COLLECT_INFO",
    "4. COLLECT_INFO: Gather income, credit score, spending habits",
    "   ├── If data incomplete → Loop back to COLLECT_INFO",
    "   └── If data complete → RECOMMEND",
    "5. RECOMMEND: Show best matching credit card",
    "   ├── If customer has concerns → OBJECTION",
    "   └── If ready to proceed → CONFIRM",
    "6. OBJECTION: Address customer concerns/questions",
    "   ├── If resolved → RECOMMEND (try again)",
    "   └── If can't resolve → END (Call ends)",
    "7. CONFIRM: Get final yes/no from customer",
    "8. SAVE_TO_DB: Record call outcome and update lead status",
    "9. END: Call successfully completed"
]

for step in flow_steps:
    print(step)

print("\n" + "=" * 60)
print("🎯 KEY FEATURES:")
print("=" * 60)
print("• State persistence via Redis")
print("• Turn-based conversation (one node per API call)")
print("• Dynamic routing based on customer responses")
print("• Data collection loop until complete")
print("• Objection handling with retry logic")
print("• Multiple exit points (success/failure)")
print("=" * 60)