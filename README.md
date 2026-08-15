# Triad-of-Agents
A2A + MCP + CrewAI + ADK + PydanticAI


```
Customer
   │
   ▼
Waiter Agent
   │
   ├── ask_ingredients("tacos")
   │          │
   │          ▼
   │    Ingredients Agent
   │          │
   │          └── taco ingredients
   │
   └── ask_chef("Prepare tacos with ...")
              │
              ▼
          Chef Agent
              │
              └── preparation confirmation
   │
   ▼
Waiter Agent
   │
   ▼
Customer
```

The system uses a Waiter Agent (made with google ADK) as the customer's single point of contact. The Waiter Agent delegates tasks to specialized agents:

 - Ingredients Agent: provides the ingredients for a requested dish. (has a tool access via MCP) (made with Pydantic AI)
 - Chef Agent: prepares the requested dish using the ingredients provided by the Ingredients Agent. (has a tool access via MCP) (made with CrewAI)

All Agents are connected to each other via A2A

<img width="1063" height="695" alt="Screenshot 2026-08-15 231458" src="https://github.com/user-attachments/assets/8f3a463d-9439-4d20-982d-6b5d0e172bb7" />
