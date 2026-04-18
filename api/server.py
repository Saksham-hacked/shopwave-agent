import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

load_dotenv()

logger = logging.getLogger("shopwave.api")

# ── Initialise data once on server startup ────────────────────────────────────
from tools.lookup import init_data
from tools.knowledge import init_knowledge_base

init_data()
init_knowledge_base()

from agent.graph import app as agent_app
from agent.utils import make_initial_state  # single source of truth — no duplication

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="ShopWave Autonomous Support Agent",
    description="LangGraph + Gemini 2.5 Flash powered customer support agent",
    version="1.0.0",
)

AUDIT_LOG_PATH = Path("audit_log.json")
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT_TICKETS", "5"))


# ── Pydantic models ───────────────────────────────────────────────────────────
class SingleTicketRequest(BaseModel):
    ticket: dict


class BatchTicketRequest(BaseModel):
    tickets: List[dict]


# ── Helpers ───────────────────────────────────────────────────────────────────
async def _run_ticket(ticket: dict) -> dict:
    try:
        initial_state = make_initial_state(ticket)
        final_state = await agent_app.ainvoke(initial_state)
        return final_state.get("audit_entry") or {}
    except Exception as e:
        logger.error(f"Ticket processing error: {e}", exc_info=True)
        return {
            "ticket_id": ticket.get("ticket_id", "unknown"),
            "resolution": "failed",
            "errors_encountered": [{"error_type": type(e).__name__, "message": str(e)}],
        }


async def _run_batch(tickets: List[dict]) -> List[dict]:
    sem = asyncio.Semaphore(MAX_CONCURRENT)

    async def _bounded(ticket):
        async with sem:
            return await _run_ticket(ticket)

    return await asyncio.gather(*[_bounded(t) for t in tickets])


def _append_to_audit_log(entries: list):
    existing = []
    if AUDIT_LOG_PATH.exists():
        try:
            with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = []
    existing.extend(entries)
    with open(AUDIT_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, default=str)


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/tickets/process")
async def process_single_ticket(request: SingleTicketRequest):
    """Process a single support ticket through the full agent pipeline."""
    if not request.ticket:
        raise HTTPException(status_code=400, detail="ticket body is required")

    audit_entry = await _run_ticket(request.ticket)
    _append_to_audit_log([audit_entry])
    return JSONResponse(content=audit_entry)


@app.post("/tickets/batch")
async def process_batch(request: BatchTicketRequest):
    """Process a batch of tickets concurrently."""
    if not request.tickets:
        raise HTTPException(status_code=400, detail="tickets list is required")

    audit_entries = await _run_batch(request.tickets)
    _append_to_audit_log(list(audit_entries))
    return JSONResponse(content=list(audit_entries))


@app.get("/audit-log")
async def get_audit_log():
    """Return the full audit log."""
    if not AUDIT_LOG_PATH.exists():
        return JSONResponse(content=[], status_code=200)
    try:
        with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return JSONResponse(content=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read audit log: {e}")


@app.get("/tickets/{ticket_id}/status")
async def get_ticket_status(ticket_id: str):
    """Return the audit entry for a specific processed ticket."""
    if not AUDIT_LOG_PATH.exists():
        raise HTTPException(status_code=404, detail="No audit log found. Run the agent first.")

    try:
        with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
            entries = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read audit log: {e}")

    match = next((e for e in entries if e.get("ticket_id") == ticket_id), None)
    if not match:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found in audit log")

    return JSONResponse(content=match)
