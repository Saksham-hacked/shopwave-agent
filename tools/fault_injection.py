import os
import json
import random
import asyncio
import logging
from datetime import datetime
from typing import Optional, Any

logger = logging.getLogger(__name__)

INJECT_FAULTS = os.getenv("INJECT_FAULTS", "false").lower() == "true"

FAILURE_CONFIG = {
    "check_refund_eligibility": {"timeout_rate": 0.20, "malformed_rate": 0.15, "timeout_seconds": 4.0},
    "get_order": {"timeout_rate": 0.10, "partial_rate": 0.15, "timeout_seconds": 3.0},
    "get_customer": {"timeout_rate": 0.08, "timeout_seconds": 3.0},
    "issue_refund": {"timeout_rate": 0.05, "timeout_seconds": 3.0},
    "get_product": {"timeout_rate": 0.05, "timeout_seconds": 2.0},
}

NON_CRITICAL_FIELDS = {
    "get_order": ["notes", "tracking_number"],
    "get_customer": ["phone", "notes"],
    "get_product": ["notes"],
}


async def call_with_retry(tool_name: str, coro_factory, state: dict, max_retries: int = 3) -> Optional[Any]:
    config = FAILURE_CONFIG.get(tool_name, {})
    timeout_rate = config.get("timeout_rate", 0.0) if INJECT_FAULTS else 0.0
    malformed_rate = config.get("malformed_rate", 0.0) if INJECT_FAULTS else 0.0
    partial_rate = config.get("partial_rate", 0.0) if INJECT_FAULTS else 0.0
    timeout_seconds = config.get("timeout_seconds", 5.0)

    last_error = None
    for attempt in range(1, max_retries + 1):
        start_time = asyncio.get_event_loop().time()
        tool_call_entry = {
            "tool": tool_name,
            "input": {},
            "output": None,
            "status": "pending",
            "attempt": attempt,
            "duration_ms": 0,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        try:
            roll = random.random()

            # Timeout fault
            if roll < timeout_rate:
                async def timeout_coro():
                    await asyncio.sleep(timeout_seconds + 1)
                    return {}
                try:
                    result = await asyncio.wait_for(timeout_coro(), timeout=timeout_seconds)
                except asyncio.TimeoutError:
                    raise asyncio.TimeoutError(f"{tool_name} timed out after {timeout_seconds}s")

            # Malformed fault
            elif roll < timeout_rate + malformed_rate:
                result = {"__malformed__": True, "garbage": "%%%INVALID%%%"}
                raise ValueError(f"{tool_name} returned malformed response")

            else:
                # Real call
                coro = coro_factory()
                result = await asyncio.wait_for(coro, timeout=timeout_seconds)

                # Partial data fault
                if result and isinstance(result, dict) and random.random() < partial_rate:
                    drop_fields = NON_CRITICAL_FIELDS.get(tool_name, [])
                    if drop_fields:
                        field_to_drop = random.choice(drop_fields)
                        result = {k: v for k, v in result.items() if k != field_to_drop}
                        logger.debug(f"[FaultInjection] Partial data: dropped '{field_to_drop}' from {tool_name}")

            elapsed_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            tool_call_entry["output"] = result
            tool_call_entry["status"] = "success"
            tool_call_entry["duration_ms"] = elapsed_ms
            state["tool_calls"].append(tool_call_entry)
            return result

        except asyncio.TimeoutError as e:
            elapsed_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            last_error = e
            tool_call_entry["status"] = "timeout"
            tool_call_entry["duration_ms"] = elapsed_ms
            state["tool_calls"].append(tool_call_entry)
            logger.warning(f"[Retry {attempt}/{max_retries}] {tool_name} timeout: {e}")
            if attempt < max_retries:
                backoff = 0.3 * (2 ** (attempt - 1))
                await asyncio.sleep(backoff)

        except ValueError as e:
            elapsed_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            last_error = e
            tool_call_entry["status"] = "malformed"
            tool_call_entry["duration_ms"] = elapsed_ms
            state["tool_calls"].append(tool_call_entry)
            logger.warning(f"[Retry {attempt}/{max_retries}] {tool_name} malformed: {e}")
            if attempt < max_retries:
                backoff = 0.3 * (2 ** (attempt - 1))
                await asyncio.sleep(backoff)

        except Exception as e:
            elapsed_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            last_error = e
            tool_call_entry["status"] = "error"
            tool_call_entry["duration_ms"] = elapsed_ms
            state["tool_calls"].append(tool_call_entry)
            logger.warning(f"[Retry {attempt}/{max_retries}] {tool_name} error: {e}")
            if attempt < max_retries:
                backoff = 0.3 * (2 ** (attempt - 1))
                await asyncio.sleep(backoff)

    # Exhausted all retries
    error_entry = {
        "tool": tool_name,
        "error_type": type(last_error).__name__,
        "message": str(last_error),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    state["errors"].append(error_entry)

    exhausted_entry = {
        "tool": tool_name,
        "input": {},
        "output": None,
        "status": "exhausted",
        "attempt": max_retries,
        "duration_ms": 0,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    state["tool_calls"].append(exhausted_entry)
    logger.error(f"[DeadLetter] {tool_name} exhausted after {max_retries} retries: {last_error}")
    return None
