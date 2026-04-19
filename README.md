# ShopWave Autonomous Support Agent

An autonomous customer support agent built with **LangGraph + Google Gemini 2.5 Flash + FastAPI** that processes 20 support tickets concurrently, resolves them using a multi-step reasoning chain, and escalates intelligently when uncertain.

---

## Overview

ShopWave Agent is a production-grade, fully autonomous support system. It ingests customer tickets, classifies them, fetches order/customer/product context, executes multi-step tool chains (ReAct loop), decides on a resolution, and logs every action to a structured audit trail — all without human intervention.

**Key capabilities:**
- Concurrent processing of 20 tickets via `asyncio.gather` + `Semaphore(5)`
- 6-node LangGraph `StateGraph` with conditional routing
- 9 async tools with realistic fault injection and retry logic
- Confidence scoring at every node — auto-escalates below 0.6
- Social engineering detection pre-routed before any tool calls
- Full audit log written to `audit_log.json`

---

## Tech Stack

| Layer | Technology |
|---|---|
| Orchestration | LangGraph `StateGraph` |
| LLM | Google Gemini 2.5 Flash (`gemini-2.5-flash-preview-04-17`) |
| API | FastAPI + uvicorn |
| Concurrency | Python `asyncio` — `Semaphore(5)` + `asyncio.gather` |
| Config | `python-dotenv` |
| Logging | Python `logging` → stdout + `audit_log.json` |

---

## Project Structure

```
shopwave-agent/
├── main.py                    # Entry point: python main.py
├── requirements.txt
├── .env.example
├── README.md
├── setup.md
├── failure_modes.md
├── audit_log.json             # Auto-generated on run
├── agent/
│   ├── __init__.py
│   ├── state.py               # TicketState TypedDict
│   ├── graph.py               # LangGraph StateGraph
│   ├── nodes.py               # All 6 node functions
│   └── router.py              # Conditional edge logic
├── tools/
│   ├── __init__.py
│   ├── lookup.py              # get_customer, get_order, get_product
│   ├── knowledge.py           # search_knowledge_base
│   ├── actions.py             # issue_refund, send_reply, escalate, cancel_order
│   └── fault_injection.py     # Mock failures + retry logic
├── data/
│   ├── customers.json         # 10 customers (C001–C010)
│   ├── orders.json            # 15 orders (ORD-1001–ORD-1015)
│   ├── products.json          # 8 products (P001–P008)
│   ├── knowledge_base.md      # ShopWave policy document
│   └── tickets.json           # 20 support tickets (TKT-001–TKT-020)
└── api/
    ├── __init__.py
    └── server.py              # FastAPI app
```

---

## Setup & Installation

visit https://shopwave-agent.vercel.app/

**Quick start:**

```bash
git clone https://github.com/Saksham-hacked/shopwave-agent
cd shopwave-agent
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
python main.py
```

---

## Running the Agent

### Process all 20 tickets

```bash
python main.py
```

Live progress is printed per ticket:

```
[1/20] TKT-001 ✓ resolved     (confidence: 0.91, tools: 5, 1.24s)
[2/20] TKT-002 ✓ resolved     (confidence: 0.85, tools: 4, 0.98s)
...
```

Final summary:

```
=== SHOPWAVE AGENT RUN COMPLETE ===
Total: 20 | Resolved: 14 | Escalated: 4 | Clarified: 2 | Failed: 0
Avg confidence: 0.81 | Total tool calls: 87 | Errors recovered: 3
Audit log written to: audit_log.json
```

### Run the API server

```bash
uvicorn api.server:app --reload --port 8000
```

API docs available at: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/tickets/process` | Process a single ticket |
| `POST` | `/tickets/batch` | Process a batch of tickets concurrently |
| `GET` | `/audit-log` | Retrieve the full audit log |
| `GET` | `/tickets/{ticket_id}/status` | Get status of a specific ticket |

**Example — single ticket:**

```bash
curl -X POST http://localhost:8000/tickets/process \
  -H "Content-Type: application/json" \
  -d '{"ticket": {"ticket_id": "TKT-001", "customer_email": "alice.turner@email.com", "subject": "Headphones stopped working", "body": "My order ORD-1001 headphones broke after 2 weeks.", "order_id": "ORD-1001"}}'
```

---

## Agent Architecture

```
Ticket Input
    │
    ▼
┌─────────────────────────────────────────────┐
│           LangGraph StateGraph              │
│                                             │
│  [1] classify_and_triage                   │
│        │                                    │
│        ├─ social_engineering ──────────────┐│
│        ▼                                   ││
│  [2] fetch_context                         ││
│      (get_customer ║ get_order → product)  ││
│        │                                   ││
│        ▼                                   ││
│  [3] tool_execution  (ReAct loop)          ││
│      check_eligibility → issue_refund      ││
│      cancel_order / search_kb / escalate   ││
│        │                                   ││
│        ▼                                   ││
│  [4] decide_resolution ◄───────────────────┘│
│      resolved / escalated / clarify         │
│        │                                    │
│        ▼                                    │
│  [5] execute_resolution                    │
│        │                                    │
│        ▼                                    │
│  [6] audit_logger → audit_log.json         │
└─────────────────────────────────────────────┘
```

---

## Key Design Decisions

**Confidence scoring at every node**
Each node updates a running confidence score. Any ticket falling below 0.6 is automatically escalated regardless of the LLM's resolution suggestion.

**Refund guard**
`issue_refund` checks `state["tool_calls"]` for a prior successful `check_refund_eligibility` call. Calling `issue_refund` without the eligibility check returns an error and logs a policy flag — it never silently processes an ineligible refund.

**Social engineering pre-routing**
Tickets classified as `social_engineering` skip `fetch_context` and `tool_execution` entirely. They are routed directly to `decide_resolution` with `resolution="escalated"` and `priority="urgent"` — no refund tools are ever called.

**Dead-letter queue**
Every failed tool call (after 3 retry attempts) is appended to `state["errors"]` and logged in the audit trail. The agent never silently drops failures.

**Fault injection**
Set `INJECT_FAULTS=true` in `.env` (default for demo runs) to simulate realistic tool failures: timeouts, malformed responses, and partial data. The retry logic handles these with exponential backoff (0.3s → 0.6s → 1.2s).

**Concurrent processing**
`asyncio.Semaphore(5)` limits concurrent ticket workers to 5. `asyncio.gather` runs all 20 tickets in parallel within that limit. Each ticket gets a completely independent `TicketState` — no shared mutable state.

---

## Audit Log

Every processed ticket produces a structured record in `audit_log.json`:

```json
{
  "ticket_id": "TKT-001",
  "timestamp": "2024-03-15T09:12:00Z",
  "processing_time_ms": 1234,
  "customer_email": "alice.turner@email.com",
  "customer_tier": "vip",
  "classification": {"category": "refund_request", "urgency": "medium", "confidence": 0.92},
  "confidence_trace": [0.92, 0.92, 0.87, 0.87],
  "tool_calls": [...],
  "tool_calls_count": 5,
  "reasoning_steps": [...],
  "resolution": "resolved",
  "reply_sent": true,
  "escalated": false,
  "errors_encountered": [],
  "policy_flags": []
}
```

---

## Failure Mode Handling

See [`failure_modes.md`](./failure_modes.md) for full analysis of all 6 failure scenarios including tool timeouts, malformed LLM responses, social engineering, missing customers, and refund guard violations.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *(required)* | Google Gemini API key |
| `INJECT_FAULTS` | `true` | Enable fault injection for demo runs |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `MAX_CONCURRENT_TICKETS` | `5` | Semaphore limit for concurrent workers |
| `MAX_TOOL_RETRIES` | `3` | Max retry attempts per tool call |
