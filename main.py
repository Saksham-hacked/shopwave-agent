# import asyncio
# import json
# import logging
# import os
# import sys
# import time
# from pathlib import Path

# from dotenv import load_dotenv

# load_dotenv()

# # ── Logging setup ────────────────────────────────────────────────────────────
# log_level = os.getenv("LOG_LEVEL", "INFO").upper()
# logging.basicConfig(
#     level=getattr(logging, log_level, logging.INFO),
#     format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
#     handlers=[
#         logging.StreamHandler(sys.stdout),
#         logging.FileHandler("shopwave_agent.log", encoding="utf-8"),
#     ],
# )
# logger = logging.getLogger("shopwave.main")

# # ── Data initialisation (must happen before graph import) ────────────────────
# from tools.lookup import init_data
# from tools.knowledge import init_knowledge_base

# init_data()
# init_knowledge_base()

# # ── Graph import (after data is ready) ───────────────────────────────────────
# from agent.graph import app
# from agent.state import TicketState
# from agent.utils import make_initial_state  # single source of truth

# # ── Constants ─────────────────────────────────────────────────────────────────
# MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT_TICKETS", "5"))
# AUDIT_LOG_PATH = Path("audit_log.json")
# TICKETS_PATH = Path("data/tickets.json")


# async def process_ticket(
#     ticket: dict,
#     sem: asyncio.Semaphore,
#     index: int,
#     progress_lock: asyncio.Lock,
#     counter: list,  # counter[0] = completed count — list avoids nonlocal closure issues
#     total: int,
# ) -> dict:
#     """Process a single ticket.  Never raises — returns a 'failed' audit entry on error."""
#     ticket_id = ticket.get("ticket_id", f"TKT-{index:03d}")
#     start = time.time()

#     async with sem:
#         try:
#             initial_state = make_initial_state(ticket)
#             final_state = await app.ainvoke(initial_state)
#             audit = final_state.get("audit_entry") or {}

#             resolution = audit.get("resolution", "unknown")
#             confidence = (
#                 audit.get("confidence_trace", [0.0])[-1]
#                 if audit.get("confidence_trace")
#                 else final_state.get("confidence", 0.0)
#             )
#             tools_called = audit.get("tool_calls_count", len(final_state.get("tool_calls", [])))
#             elapsed = time.time() - start

#             sym = {"resolved": "✓", "escalated": "↑", "clarify": "?", "failed": "✗"}.get(resolution, "~")

#             async with progress_lock:
#                 counter[0] += 1
#                 print(
#                     f"[{counter[0]:2d}/{total}] {ticket_id} {sym} {resolution:<10s}"
#                     f" (confidence: {confidence:.2f}, tools: {tools_called}, {elapsed:.2f}s)"
#                 )

#             return audit

#         except Exception as e:
#             elapsed = time.time() - start
#             logger.error(f"[{ticket_id}] Unhandled exception in process_ticket: {e}", exc_info=True)

#             import datetime

#             failed_entry = {
#                 "ticket_id": ticket_id,
#                 "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
#                 "processing_time_ms": int(elapsed * 1000),
#                 "customer_email": ticket.get("customer_email", ""),
#                 "customer_tier": "unknown",
#                 "classification": None,
#                 "confidence_trace": [],
#                 "tool_calls": [],
#                 "tool_calls_count": 0,
#                 "reasoning_steps": [],
#                 "resolution": "failed",
#                 "reply_sent": False,
#                 "reply_message": None,
#                 "escalated": False,
#                 "escalation_summary": None,
#                 "errors_encountered": [
#                     {
#                         "tool": "process_ticket",
#                         "error_type": type(e).__name__,
#                         "message": str(e),
#                         "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
#                     }
#                 ],
#                 "policy_flags": [],
#                 "refund_issued": False,
#             }

#             async with progress_lock:
#                 counter[0] += 1
#                 print(
#                     f"[{counter[0]:2d}/{total}] {ticket_id} ✗ failed"
#                     f"      (unhandled error: {type(e).__name__})"
#                 )

#             return failed_entry


# async def run_all_tickets():
#     """Load all tickets and process them concurrently.  Safe to call multiple times."""
#     # Load tickets
#     if not TICKETS_PATH.exists():
#         logger.error(f"Tickets file not found: {TICKETS_PATH}")
#         sys.exit(1)

#     with open(TICKETS_PATH, "r", encoding="utf-8") as f:
#         tickets = json.load(f)

#     total = len(tickets)
#     print(f"\nLoading data files... done")
#     print(f"Starting ShopWave Agent — processing {total} tickets (max {MAX_CONCURRENT} concurrent)\n")

#     sem = asyncio.Semaphore(MAX_CONCURRENT)
#     progress_lock = asyncio.Lock()
#     counter = [0]  # mutable container so counter resets cleanly on every call

#     tasks = [
#         process_ticket(ticket, sem, idx + 1, progress_lock, counter, total)
#         for idx, ticket in enumerate(tickets)
#     ]

#     audit_entries = await asyncio.gather(*tasks)

#     # Write audit log
#     with open(AUDIT_LOG_PATH, "w", encoding="utf-8") as f:
#         json.dump(list(audit_entries), f, indent=2, default=str)

#     # Summary stats
#     resolutions = [e.get("resolution", "unknown") for e in audit_entries]
#     resolved_count = resolutions.count("resolved")
#     escalated_count = resolutions.count("escalated")
#     clarified_count = resolutions.count("clarify")
#     failed_count = resolutions.count("failed")

#     all_confidences = [
#         e["confidence_trace"][-1]
#         for e in audit_entries
#         if e.get("confidence_trace")
#     ]
#     avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
#     total_tool_calls = sum(e.get("tool_calls_count", 0) for e in audit_entries)
#     total_errors = sum(len(e.get("errors_encountered", [])) for e in audit_entries)

#     print(
#         f"\n{'='*50}\n"
#         f"=== SHOPWAVE AGENT RUN COMPLETE ===\n"
#         f"{'='*50}\n"
#         f"Total: {total} | Resolved: {resolved_count} | Escalated: {escalated_count} "
#         f"| Clarified: {clarified_count} | Failed: {failed_count}\n"
#         f"Avg confidence: {avg_confidence:.2f} | Total tool calls: {total_tool_calls} "
#         f"| Errors recovered: {total_errors}\n"
#         f"Audit log written to: {AUDIT_LOG_PATH}\n"
#         f"{'='*50}"
#     )


# if __name__ == "__main__":
#     asyncio.run(run_all_tickets())
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Logging setup ────────────────────────────────────────────────────────────
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("shopwave_agent.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("shopwave.main")

# ── Data initialisation (must happen before graph import) ────────────────────
from tools.lookup import init_data
from tools.knowledge import init_knowledge_base

init_data()
init_knowledge_base()

# ── Graph import (after data is ready) ───────────────────────────────────────
from agent.graph import app
from agent.state import TicketState
from agent.utils import make_initial_state  # single source of truth

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT_TICKETS", "5"))
AUDIT_LOG_PATH = Path("audit_log.json")
TICKETS_PATH = Path("data/tickets.json")


def _normalize_resolution(value: str) -> str:
    v = str(value or "").strip().lower()
    if v in {"resolved", "resolve"}:
        return "resolved"
    if v in {"escalated", "escalate"}:
        return "escalated"
    if v in {"clarify", "needs_clarification", "clarification"}:
        return "clarify"
    return v or "unknown"


async def process_ticket(
    ticket: dict,
    sem: asyncio.Semaphore,
    index: int,
    progress_lock: asyncio.Lock,
    counter: list,  # counter[0] = completed count — list avoids nonlocal closure issues
    total: int,
) -> dict:
    """Process a single ticket.  Never raises — returns a 'failed' audit entry on error."""
    ticket_id = ticket.get("ticket_id", f"TKT-{index:03d}")
    start = time.time()

    async with sem:
        try:
            initial_state = make_initial_state(ticket)
            final_state = await app.ainvoke(initial_state)
            audit = final_state.get("audit_entry") or {}

            resolution = audit.get("resolution", "unknown")
            confidence = (
                audit.get("confidence_trace", [0.0])[-1]
                if audit.get("confidence_trace")
                else final_state.get("confidence", 0.0)
            )
            tools_called = audit.get("tool_calls_count", len(final_state.get("tool_calls", [])))
            elapsed = time.time() - start

            sym = {"resolved": "✓", "escalated": "↑", "clarify": "?", "failed": "✗"}.get(resolution, "~")

            async with progress_lock:
                counter[0] += 1
                print(
                    f"[{counter[0]:2d}/{total}] {ticket_id} {sym} {resolution:<10s}"
                    f" (confidence: {confidence:.2f}, tools: {tools_called}, {elapsed:.2f}s)"
                )

            return audit

        except Exception as e:
            elapsed = time.time() - start
            logger.error(f"[{ticket_id}] Unhandled exception in process_ticket: {e}", exc_info=True)

            import datetime

            failed_entry = {
                "ticket_id": ticket_id,
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "processing_time_ms": int(elapsed * 1000),
                "customer_email": ticket.get("customer_email", ""),
                "customer_tier": "unknown",
                "classification": None,
                "confidence_trace": [],
                "tool_calls": [],
                "tool_calls_count": 0,
                "reasoning_steps": [],
                "resolution": "failed",
                "reply_sent": False,
                "reply_message": None,
                "escalated": False,
                "escalation_summary": None,
                "errors_encountered": [
                    {
                        "tool": "process_ticket",
                        "error_type": type(e).__name__,
                        "message": str(e),
                        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    }
                ],
                "policy_flags": [],
                "refund_issued": False,
            }

            async with progress_lock:
                counter[0] += 1
                print(
                    f"[{counter[0]:2d}/{total}] {ticket_id} ✗ failed"
                    f"      (unhandled error: {type(e).__name__})"
                )

            return failed_entry


async def run_all_tickets():
    """Load all tickets and process them concurrently.  Safe to call multiple times."""
    # Load tickets
    if not TICKETS_PATH.exists():
        logger.error(f"Tickets file not found: {TICKETS_PATH}")
        sys.exit(1)

    with open(TICKETS_PATH, "r", encoding="utf-8") as f:
        tickets = json.load(f)

    total = len(tickets)
    print(f"\nLoading data files... done")
    print(f"Starting ShopWave Agent — processing {total} tickets (max {MAX_CONCURRENT} concurrent)\n")

    sem = asyncio.Semaphore(MAX_CONCURRENT)
    progress_lock = asyncio.Lock()
    counter = [0]  # mutable container so counter resets cleanly on every call

    tasks = [
        process_ticket(ticket, sem, idx + 1, progress_lock, counter, total)
        for idx, ticket in enumerate(tickets)
    ]

    audit_entries = await asyncio.gather(*tasks)

    # Write audit log
    with open(AUDIT_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(list(audit_entries), f, indent=2, default=str)

    # Summary stats
    resolutions = [_normalize_resolution(e.get("resolution", "unknown")) for e in audit_entries]
    resolved_count = resolutions.count("resolved")
    escalated_count = resolutions.count("escalated")
    clarified_count = resolutions.count("clarify")
    failed_count = resolutions.count("failed")

    all_confidences = [
        e["confidence_trace"][-1]
        for e in audit_entries
        if e.get("confidence_trace")
    ]
    avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
    total_tool_calls = sum(e.get("tool_calls_count", 0) for e in audit_entries)
    total_errors = sum(len(e.get("errors_encountered", [])) for e in audit_entries)

    print(
        f"\n{'='*50}\n"
        f"=== SHOPWAVE AGENT RUN COMPLETE ===\n"
        f"{'='*50}\n"
        f"Total: {total} | Resolved: {resolved_count} | Escalated: {escalated_count} "
        f"| Clarified: {clarified_count} | Failed: {failed_count}\n"
        f"Avg confidence: {avg_confidence:.2f} | Total tool calls: {total_tool_calls} "
        f"| Errors recovered: {total_errors}\n"
        f"Audit log written to: {AUDIT_LOG_PATH}\n"
        f"{'='*50}"
    )


if __name__ == "__main__":
    asyncio.run(run_all_tickets())