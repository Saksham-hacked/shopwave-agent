"""Shared utilities for the ShopWave agent."""
import time


def make_initial_state(ticket: dict) -> dict:
    """Build a fresh TicketState for one ticket. Single source of truth."""
    return {
        "ticket": ticket,
        "customer": None,
        "order": None,
        "product": None,
        "kb_results": None,
        "tool_calls": [],
        "reasoning_steps": [],
        "classification": None,
        "confidence": 1.0,
        "confidence_trace": [],
        "resolution": None,
        "reply_message": None,
        "escalation_summary": None,
        "errors": [],
        "refund_issued": False,
        "audit_entry": {},
        "policy_flags": [],
        "processing_start_time": time.time(),
    }
