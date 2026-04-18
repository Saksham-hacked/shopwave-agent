# import logging
# from datetime import datetime, date
# from typing import Optional

# from tools.fault_injection import call_with_retry

# logger = logging.getLogger(__name__)

# # Import orders data reference from lookup
# def _get_orders():
#     from tools.lookup import _orders
#     return _orders


# async def check_refund_eligibility(order_id: str, state: dict) -> dict:
#     async def _check():
#         orders = _get_orders()
#         order = next((o for o in orders if o.get("order_id") == order_id), None)
#         if not order:
#             return {"eligible": False, "reason": "Order not found", "amount": 0.0}

#         if order.get("refund_status") == "refunded":
#             return {
#                 "eligible": False,
#                 "reason": f"Refund already processed on this order",
#                 "amount": 0.0,
#                 "already_refunded": True,
#             }

#         status = order.get("status", "")
#         if status not in ("delivered",):
#             return {
#                 "eligible": False,
#                 "reason": f"Order status is '{status}' — must be delivered to refund",
#                 "amount": 0.0,
#             }

#         return_deadline_str = order.get("return_deadline")
#         if return_deadline_str:
#             try:
#                 return_deadline = date.fromisoformat(return_deadline_str)
#                 today = date.today()
#                 if today > return_deadline:
#                     return {
#                         "eligible": False,
#                         "reason": f"Return deadline {return_deadline_str} has passed (today: {today.isoformat()})",
#                         "amount": 0.0,
#                         "deadline_passed": True,
#                     }
#             except ValueError:
#                 pass

#         amount = float(order.get("amount", 0.0))
#         return {"eligible": True, "reason": "Order is within return window and eligible for refund", "amount": amount}

#     result = await call_with_retry("check_refund_eligibility", _check, state)
#     for entry in reversed(state["tool_calls"]):
#         if entry["tool"] == "check_refund_eligibility" and entry.get("input") == {}:
#             entry["input"] = {"order_id": order_id}
#             break
#     if result is None:
#         result = {"eligible": False, "reason": "Eligibility check failed after retries", "amount": 0.0}
#     return result


# async def issue_refund(order_id: str, amount: float, state: dict) -> dict:
#     # Guard: already issued
#     if state.get("refund_issued"):
#         error = {"error": "refund_already_issued", "message": "A refund has already been issued for this ticket"}
#         state["tool_calls"].append({
#             "tool": "issue_refund",
#             "input": {"order_id": order_id, "amount": amount},
#             "output": error,
#             "status": "error",
#             "attempt": 1,
#             "duration_ms": 0,
#             "timestamp": datetime.utcnow().isoformat() + "Z",
#         })
#         if "refund_guard_violation" not in state.get("policy_flags", []):
#             state.setdefault("policy_flags", []).append("refund_guard_violation")
#         return error

#     # Guard: eligibility must have been checked
#     eligibility_checked = any(
#         tc.get("tool") == "check_refund_eligibility" and tc.get("status") == "success"
#         for tc in state.get("tool_calls", [])
#     )
#     if not eligibility_checked:
#         error = {"error": "eligibility_not_checked", "message": "check_refund_eligibility must be called before issue_refund"}
#         state["tool_calls"].append({
#             "tool": "issue_refund",
#             "input": {"order_id": order_id, "amount": amount},
#             "output": error,
#             "status": "error",
#             "attempt": 1,
#             "duration_ms": 0,
#             "timestamp": datetime.utcnow().isoformat() + "Z",
#         })
#         state.setdefault("policy_flags", []).append("eligibility_check_missing")
#         return error

#     async def _issue():
#         return {
#             "success": True,
#             "order_id": order_id,
#             "amount": amount,
#             "refund_id": f"REF-{order_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
#             "timestamp": datetime.utcnow().isoformat() + "Z",
#             "message": f"Refund of ${amount:.2f} initiated successfully",
#         }

#     result = await call_with_retry("issue_refund", _issue, state)
#     for entry in reversed(state["tool_calls"]):
#         if entry["tool"] == "issue_refund" and entry.get("input") == {}:
#             entry["input"] = {"order_id": order_id, "amount": amount}
#             break

#     if result and result.get("success"):
#         state["refund_issued"] = True
#     return result or {"error": "refund_failed", "message": "Refund could not be processed after retries"}


# async def send_reply(ticket_id: str, message: str, state: dict) -> dict:
#     result = {
#         "sent": True,
#         "ticket_id": ticket_id,
#         "timestamp": datetime.utcnow().isoformat() + "Z",
#         "message_length": len(message),
#     }
#     state["reply_message"] = message
#     state["tool_calls"].append({
#         "tool": "send_reply",
#         "input": {"ticket_id": ticket_id, "message_preview": message[:120]},
#         "output": result,
#         "status": "success",
#         "attempt": 1,
#         "duration_ms": 1,
#         "timestamp": datetime.utcnow().isoformat() + "Z",
#     })
#     logger.info(f"[send_reply] {ticket_id}: reply sent ({len(message)} chars)")
#     return result


# async def escalate(ticket_id: str, summary: dict, priority: str, state: dict) -> dict:
#     valid_priorities = ("low", "medium", "high", "urgent")
#     if priority not in valid_priorities:
#         priority = "medium"

#     result = {
#         "escalated": True,
#         "ticket_id": ticket_id,
#         "priority": priority,
#         "timestamp": datetime.utcnow().isoformat() + "Z",
#         "escalation_id": f"ESC-{ticket_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
#     }
#     state["escalation_summary"] = summary
#     state["tool_calls"].append({
#         "tool": "escalate",
#         "input": {"ticket_id": ticket_id, "priority": priority, "summary": summary},
#         "output": result,
#         "status": "success",
#         "attempt": 1,
#         "duration_ms": 1,
#         "timestamp": datetime.utcnow().isoformat() + "Z",
#     })
#     logger.info(f"[escalate] {ticket_id}: escalated with priority={priority}")
#     return result


# async def cancel_order(order_id: str, state: dict) -> dict:
#     orders = _get_orders()
#     order = next((o for o in orders if o.get("order_id") == order_id), None)

#     if not order:
#         result = {"cancelled": False, "reason": "Order not found"}
#     elif order.get("status") != "processing":
#         result = {
#             "cancelled": False,
#             "reason": f"Order status is '{order.get('status')}' — only 'processing' orders can be cancelled",
#         }
#     else:
#         result = {
#             "cancelled": True,
#             "order_id": order_id,
#             "timestamp": datetime.utcnow().isoformat() + "Z",
#             "message": f"Order {order_id} has been successfully cancelled",
#         }

#     state["tool_calls"].append({
#         "tool": "cancel_order",
#         "input": {"order_id": order_id},
#         "output": result,
#         "status": "success",
#         "attempt": 1,
#         "duration_ms": 2,
#         "timestamp": datetime.utcnow().isoformat() + "Z",
#     })
#     return result


import logging
from datetime import datetime, date
from typing import Optional

from tools.fault_injection import call_with_retry

logger = logging.getLogger(__name__)

# Import orders data reference from lookup
def _get_orders():
    from tools.lookup import _orders
    return _orders


async def check_refund_eligibility(order_id: str, state: dict) -> dict:
    async def _check():
        orders = _get_orders()
        order = next((o for o in orders if o.get("order_id") == order_id), None)
        if not order:
            return {"eligible": False, "reason": "Order not found", "amount": 0.0}

        if order.get("refund_status") == "refunded":
            return {
                "eligible": False,
                "reason": f"Refund already processed on this order",
                "amount": 0.0,
                "already_refunded": True,
            }

        status = order.get("status", "")
        if status not in ("delivered",):
            return {
                "eligible": False,
                "reason": f"Order status is '{status}' — must be delivered to refund",
                "amount": 0.0,
            }

        return_deadline_str = order.get("return_deadline")
        if return_deadline_str:
            try:
                return_deadline = date.fromisoformat(return_deadline_str)
                today = date.today()
                if today > return_deadline:
                    return {
                        "eligible": False,
                        "reason": f"Return deadline {return_deadline_str} has passed (today: {today.isoformat()})",
                        "amount": 0.0,
                        "deadline_passed": True,
                    }
            except ValueError:
                pass

        amount = float(order.get("amount", 0.0))
        return {"eligible": True, "reason": "Order is within return window and eligible for refund", "amount": amount}

    result = await call_with_retry("check_refund_eligibility", _check, state)
    for entry in reversed(state["tool_calls"]):
        if entry["tool"] == "check_refund_eligibility" and entry.get("input") == {}:
            entry["input"] = {"order_id": order_id}
            break
    if result is None:
        result = {"eligible": False, "reason": "Eligibility check failed after retries", "amount": 0.0}
    return result


async def issue_refund(order_id: str, amount: float, state: dict) -> dict:
    # Guard: already issued
    if state.get("refund_issued"):
        error = {"error": "refund_already_issued", "message": "A refund has already been issued for this ticket"}
        state["tool_calls"].append({
            "tool": "issue_refund",
            "input": {"order_id": order_id, "amount": amount},
            "output": error,
            "status": "error",
            "attempt": 1,
            "duration_ms": 0,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })
        if "refund_guard_violation" not in state.get("policy_flags", []):
            state.setdefault("policy_flags", []).append("refund_guard_violation")
        return error

    # Guard: latest successful eligibility check must exist for THIS order
    latest_eligibility = None
    for tc in reversed(state.get("tool_calls", [])):
        if tc.get("tool") != "check_refund_eligibility":
            continue
        if tc.get("status") != "success":
            continue
        tc_input = tc.get("input") or {}
        if tc_input.get("order_id") != order_id:
            continue
        latest_eligibility = tc
        break

    if not latest_eligibility:
        error = {
            "error": "eligibility_not_checked",
            "message": "A successful check_refund_eligibility for this order must be called before issue_refund",
        }
        state["tool_calls"].append({
            "tool": "issue_refund",
            "input": {"order_id": order_id, "amount": amount},
            "output": error,
            "status": "error",
            "attempt": 1,
            "duration_ms": 0,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })
        if "eligibility_check_missing" not in state.get("policy_flags", []):
            state.setdefault("policy_flags", []).append("eligibility_check_missing")
        return error

    eligibility_output = latest_eligibility.get("output") or {}
    if not eligibility_output.get("eligible", False):
        error = {
            "error": "refund_ineligible",
            "message": f"Refund blocked: order is not eligible ({eligibility_output.get('reason', 'unknown reason')})",
            "blocked_by_policy": True,
        }
        state["tool_calls"].append({
            "tool": "issue_refund",
            "input": {"order_id": order_id, "amount": amount},
            "output": error,
            "status": "error",
            "attempt": 1,
            "duration_ms": 0,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })
        if "refund_ineligible_blocked" not in state.get("policy_flags", []):
            state.setdefault("policy_flags", []).append("refund_ineligible_blocked")
        return error

    async def _issue():
        return {
            "success": True,
            "order_id": order_id,
            "amount": amount,
            "refund_id": f"REF-{order_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "message": f"Refund of ${amount:.2f} initiated successfully",
        }

    result = await call_with_retry("issue_refund", _issue, state)
    for entry in reversed(state["tool_calls"]):
        if entry["tool"] == "issue_refund" and entry.get("input") == {}:
            entry["input"] = {"order_id": order_id, "amount": amount}
            break

    if result and result.get("success"):
        state["refund_issued"] = True
    return result or {"error": "refund_failed", "message": "Refund could not be processed after retries"}


async def send_reply(ticket_id: str, message: str, state: dict) -> dict:
    result = {
        "sent": True,
        "ticket_id": ticket_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "message_length": len(message),
    }
    state["reply_message"] = message
    state["tool_calls"].append({
        "tool": "send_reply",
        "input": {"ticket_id": ticket_id, "message_preview": message[:120]},
        "output": result,
        "status": "success",
        "attempt": 1,
        "duration_ms": 1,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })
    logger.info(f"[send_reply] {ticket_id}: reply sent ({len(message)} chars)")
    return result


async def escalate(ticket_id: str, summary: dict, priority: str, state: dict) -> dict:
    valid_priorities = ("low", "medium", "high", "urgent")
    if priority not in valid_priorities:
        priority = "medium"

    result = {
        "escalated": True,
        "ticket_id": ticket_id,
        "priority": priority,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "escalation_id": f"ESC-{ticket_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
    }
    state["escalation_summary"] = summary
    state["tool_calls"].append({
        "tool": "escalate",
        "input": {"ticket_id": ticket_id, "priority": priority, "summary": summary},
        "output": result,
        "status": "success",
        "attempt": 1,
        "duration_ms": 1,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })
    logger.info(f"[escalate] {ticket_id}: escalated with priority={priority}")
    return result


async def cancel_order(order_id: str, state: dict) -> dict:
    orders = _get_orders()
    order = next((o for o in orders if o.get("order_id") == order_id), None)

    if not order:
        result = {"cancelled": False, "reason": "Order not found"}
    elif order.get("status") != "processing":
        result = {
            "cancelled": False,
            "reason": f"Order status is '{order.get('status')}' — only 'processing' orders can be cancelled",
        }
    else:
        result = {
            "cancelled": True,
            "order_id": order_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "message": f"Order {order_id} has been successfully cancelled",
        }

    state["tool_calls"].append({
        "tool": "cancel_order",
        "input": {"order_id": order_id},
        "output": result,
        "status": "success",
        "attempt": 1,
        "duration_ms": 2,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })
    return result