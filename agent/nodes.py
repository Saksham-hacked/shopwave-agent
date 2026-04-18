# import os
# import json
# import logging
# import asyncio
# import re
# from datetime import datetime, timezone
# from typing import Optional

# from google import genai
# from google.genai import types as genai_types

# from agent.state import TicketState
# from tools.lookup import get_customer, get_order, get_product, get_orders_for_customer
# from tools.knowledge import search_knowledge_base
# from tools.actions import (
#     check_refund_eligibility,
#     issue_refund,
#     send_reply,
#     escalate,
#     cancel_order,
# )

# logger = logging.getLogger(__name__)

# # Configure Gemini — new google-genai SDK
# _api_key = os.getenv("GEMINI_API_KEY", "")
# _client = genai.Client(api_key=_api_key) if _api_key else None

# GEMINI_MODEL = "gemini-2.5-flash"

# # Categories where it makes sense to auto-look up most-recent order when none is provided.
# # Ambiguous and policy_question tickets should NOT get a random order silently attached.
# _ORDER_LOOKUP_CATEGORIES = {
#     "refund_request",
#     "return_request",
#     "order_status",
#     "cancellation",
#     "warranty_claim",
#     "damaged_item",
#     "wrong_item",
# }


# def _extract_json(text: str) -> Optional[dict]:
#     """Extract JSON from LLM response, handling markdown fences."""
#     text = text.strip()
#     # Strip markdown fences
#     text = re.sub(r"^```(?:json)?\s*", "", text)
#     text = re.sub(r"\s*```$", "", text)
#     text = text.strip()
#     try:
#         return json.loads(text)
#     except json.JSONDecodeError:
#         # Try to find first { ... } block
#         match = re.search(r"\{.*\}", text, re.DOTALL)
#         if match:
#             try:
#                 return json.loads(match.group())
#             except json.JSONDecodeError:
#                 pass
#     return None


# async def _gemini_call(prompt: str, retry: bool = True):
#     """Call Gemini and return parsed JSON (dict or list). Returns None on failure."""
#     if _client is None:
#         logger.error("Gemini client not initialised — GEMINI_API_KEY missing")
#         return None

#     loop = asyncio.get_running_loop()
#     for attempt in range(2):
#         try:
#             current_prompt = prompt
#             response = await loop.run_in_executor(
#                 None,
#                 lambda p=current_prompt: _client.models.generate_content(
#                     model=GEMINI_MODEL,
#                     contents=p,
#                     config=genai_types.GenerateContentConfig(temperature=0.1),
#                 ),
#             )
#             text = response.text
#             parsed = _extract_json(text)
#             if parsed is not None:
#                 return parsed
#             if attempt == 0 and retry:
#                 logger.warning("Gemini returned non-JSON, retrying with stricter prompt")
#                 prompt = prompt + "\n\nCRITICAL: Return ONLY valid JSON. No markdown, no prose, no explanation."
#             else:
#                 logger.error(f"Gemini JSON parse failed after {attempt+1} attempts. Raw: {text[:200]}")
#                 return None
#         except Exception as e:
#             logger.error(f"Gemini API error (attempt {attempt+1}): {e}")
#             if attempt == 0 and retry:
#                 await asyncio.sleep(1.0)
#             else:
#                 return None
#     return None


# # ─────────────────────────────────────────────
# # NODE 1: classify_and_triage
# # ─────────────────────────────────────────────
# async def classify_and_triage(state: TicketState) -> dict:
#     ticket = state["ticket"]
#     ticket_id = ticket.get("ticket_id", "UNKNOWN")

#     try:
#         # Search KB for context
#         query = f"{ticket.get('subject', '')} {ticket.get('body', '')}"
#         kb_results = await search_knowledge_base(query[:300], state)
#         state["kb_results"] = kb_results

#         prompt = f"""You are a support triage agent for ShopWave, an e-commerce platform.
# Classify the following support ticket and return ONLY valid JSON.

# Ticket ID: {ticket.get('ticket_id')}
# Subject: {ticket.get('subject')}
# Body: {ticket.get('body')}
# Customer Email: {ticket.get('customer_email')}
# Order ID in ticket: {ticket.get('order_id', 'not provided')}

# Return JSON with exactly these keys:
# {{
#   "category": "<one of: refund_request | return_request | order_status | cancellation | warranty_claim | damaged_item | wrong_item | policy_question | social_engineering | ambiguous>",
#   "urgency": "<one of: low | medium | high | urgent>",
#   "resolvability": "<one of: auto_resolvable | needs_escalation | needs_clarification>",
#   "confidence": <float 0.0 to 1.0>,
#   "reasoning": "<one sentence explaining classification>",
#   "order_id": "<order ID string extracted from ticket body, or null>",
#   "customer_email": "<customer email string>"
# }}

# Rules:
# - social_engineering: customer claims policies or tier benefits that do not exist or cannot be verified
# - warranty_claim: product defect reported but return window likely expired
# - damaged_item: product arrived physically broken/damaged
# - wrong_item: wrong size, color, or product delivered
# - ambiguous: ticket lacks enough info to classify confidently"""

#         parsed = await _gemini_call(prompt)

#         if parsed is None:
#             # Fallback classification
#             parsed = {
#                 "category": "ambiguous",
#                 "urgency": "medium",
#                 "resolvability": "needs_escalation",
#                 "confidence": 0.3,
#                 "reasoning": "LLM classification failed — defaulting to ambiguous escalation",
#                 "order_id": ticket.get("order_id"),
#                 "customer_email": ticket.get("customer_email", ""),
#             }
#             state["policy_flags"].append("llm_classification_failed")

#         # Validate required fields
#         required_fields = ["category", "urgency", "resolvability", "confidence"]
#         for f in required_fields:
#             if f not in parsed:
#                 parsed[f] = {"category": "ambiguous", "urgency": "medium", "resolvability": "needs_escalation", "confidence": 0.3}[f]

#         # Override order_id from ticket if LLM missed it
#         if not parsed.get("order_id") and ticket.get("order_id"):
#             parsed["order_id"] = ticket["order_id"]

#         state["classification"] = parsed
#         state["confidence"] = float(parsed.get("confidence", 0.5))
#         state["confidence_trace"].append(state["confidence"])

#         step = f"Classified as {parsed.get('category')} with {parsed.get('urgency')} urgency. Confidence: {state['confidence']:.2f}"
#         state["reasoning_steps"].append(step)
#         logger.info(f"[{ticket_id}] {step}")

#     except Exception as e:
#         logger.error(f"[{ticket_id}] classify_and_triage exception: {e}")
#         state["classification"] = {
#             "category": "ambiguous",
#             "urgency": "medium",
#             "resolvability": "needs_escalation",
#             "confidence": 0.3,
#             "reasoning": f"Node exception: {str(e)}",
#             "order_id": ticket.get("order_id"),
#             "customer_email": ticket.get("customer_email", ""),
#         }
#         state["confidence"] = 0.3
#         state["confidence_trace"].append(0.3)
#         state["errors"].append({
#             "tool": "classify_and_triage",
#             "error_type": type(e).__name__,
#             "message": str(e),
#             "timestamp": datetime.utcnow().isoformat() + "Z",
#         })

#     return {
#         "classification": state["classification"],
#         "confidence": state["confidence"],
#         "confidence_trace": state["confidence_trace"],
#         "kb_results": state.get("kb_results"),
#     }


# # ─────────────────────────────────────────────
# # NODE 2: fetch_context
# # ─────────────────────────────────────────────
# async def fetch_context(state: TicketState) -> dict:
#     ticket = state["ticket"]
#     classification = state.get("classification") or {}
#     ticket_id = ticket.get("ticket_id", "UNKNOWN")

#     try:
#         customer_email = classification.get("customer_email") or ticket.get("customer_email", "")
#         order_id = classification.get("order_id") or ticket.get("order_id")

#         # Run customer and order fetches concurrently
#         tasks = [get_customer(customer_email, state)]
#         if order_id:
#             tasks.append(get_order(order_id, state))

#         results = await asyncio.gather(*tasks, return_exceptions=True)

#         customer = results[0] if not isinstance(results[0], Exception) else None
#         order = None
#         if len(results) > 1:
#             order = results[1] if not isinstance(results[1], Exception) else None

#         # ── Bug 5 fix ──────────────────────────────────────────────────────────
#         # Only fall back to "most-recent order" when:
#         #   (a) no order_id was provided in the ticket, AND
#         #   (b) the ticket category is one that genuinely involves an order
#         #       (not ambiguous, policy_question, or social_engineering).
#         # This prevents TKT-020 (ambiguous, no order) from silently attaching a
#         # random order and drifting into an unintended refund path.
#         category = classification.get("category", "ambiguous")
#         if not order and not order_id and customer and category in _ORDER_LOOKUP_CATEGORIES:
#             customer_orders = get_orders_for_customer(customer["customer_id"])
#             if customer_orders:
#                 # Take the most recent order
#                 latest = sorted(customer_orders, key=lambda o: o.get("order_date", ""), reverse=True)[0]
#                 order = await get_order(latest["order_id"], state)
#                 if order:
#                     state["reasoning_steps"].append(
#                         f"No order_id in ticket — resolved most-recent order {order['order_id']} for category={category}"
#                     )

#         # Fetch product if order is available
#         product = None
#         if order and order.get("product_id"):
#             product = await get_product(order["product_id"], state)

#         # Adjust confidence based on missing context
#         confidence = state["confidence"]
#         if not customer:
#             confidence = max(0.0, confidence - 0.1)
#             state["reasoning_steps"].append("Customer not found in system — confidence reduced")
#         if order_id and not order:
#             confidence = max(0.0, confidence - 0.1)
#             state["reasoning_steps"].append("Order not found in system — confidence reduced")

#         state["customer"] = customer
#         state["order"] = order
#         state["product"] = product
#         state["confidence"] = confidence
#         state["confidence_trace"].append(confidence)

#         customer_tier = customer.get("tier", "unknown") if customer else "not found"
#         order_status = order.get("status", "unknown") if order else "not found"
#         product_name = product.get("name", "unknown") if product else "not found"

#         step = f"Fetched context: customer={customer_tier}, order={order_status}, product={product_name}"
#         state["reasoning_steps"].append(step)
#         logger.info(f"[{ticket_id}] {step}")

#     except Exception as e:
#         logger.error(f"[{ticket_id}] fetch_context exception: {e}")
#         state["errors"].append({
#             "tool": "fetch_context",
#             "error_type": type(e).__name__,
#             "message": str(e),
#             "timestamp": datetime.utcnow().isoformat() + "Z",
#         })

#     return {
#         "customer": state.get("customer"),
#         "order": state.get("order"),
#         "product": state.get("product"),
#         "confidence": state["confidence"],
#         "confidence_trace": state["confidence_trace"],
#     }


# # ─────────────────────────────────────────────
# # NODE 3: tool_execution (ReAct loop)
# # ─────────────────────────────────────────────
# async def tool_execution(state: TicketState) -> dict:
#     ticket = state["ticket"]
#     ticket_id = ticket.get("ticket_id", "UNKNOWN")
#     classification = state.get("classification") or {}
#     customer = state.get("customer")
#     order = state.get("order")
#     product = state.get("product")

#     TOOL_DESCRIPTIONS = """
# Available tools:
# 1. get_customer(email) - Fetch customer profile by email
# 2. get_order(order_id) - Fetch order details by order ID
# 3. get_product(product_id) - Fetch product info by product ID
# 4. search_knowledge_base(query) - Search ShopWave policy KB
# 5. check_refund_eligibility(order_id) - Check if order is eligible for refund (MUST be called before issue_refund)
# 6. issue_refund(order_id, amount) - Issue a refund (requires prior eligibility check)
# 7. send_reply(ticket_id, message) - Send reply to customer
# 8. escalate(ticket_id, summary_dict, priority) - Escalate ticket
# 9. cancel_order(order_id) - Cancel an order (only works if status=processing)
# """

#     try:
#         prompt = f"""You are a ShopWave support agent executing tools to resolve a customer ticket.

# TICKET:
# ID: {ticket.get('ticket_id')}
# Subject: {ticket.get('subject')}
# Body: {ticket.get('body')}

# CLASSIFICATION: {json.dumps(classification, indent=2)}

# CUSTOMER: {json.dumps(customer, indent=2) if customer else 'NOT FOUND'}
# ORDER: {json.dumps(order, indent=2) if order else 'NOT FOUND'}
# PRODUCT: {json.dumps(product, indent=2) if product else 'NOT FOUND'}
# KB RESULTS (summary): {str(state.get('kb_results', ''))[:800]}

# {TOOL_DESCRIPTIONS}

# RULES:
# - You MUST plan at least 3 tool calls
# - For refund requests: ALWAYS call check_refund_eligibility BEFORE issue_refund
# - For warranty claims: do NOT issue refund — escalate instead
# - For social_engineering: do NOT call refund tools — escalate with urgent priority
# - For order_status with shipped order: look up tracking, do NOT offer refund
# - For cancellation: call cancel_order only if order exists
# - For policy_question: use search_knowledge_base then send_reply

# Return a JSON array of tool calls to execute:
# [
#   {{"tool_name": "<tool>", "arguments": {{...}}, "reasoning": "<why this tool>"}},
#   ...
# ]
# Return ONLY the JSON array, no prose."""

#         parsed = await _gemini_call(prompt)

#         # Handle if response is a list directly
#         tool_plan = None
#         if isinstance(parsed, list):
#             tool_plan = parsed
#         elif isinstance(parsed, dict) and "tool_calls" in parsed:
#             tool_plan = parsed["tool_calls"]
#         elif isinstance(parsed, dict):
#             # Maybe it's a single tool call
#             tool_plan = [parsed]

#         if not tool_plan:
#             # Fallback: minimal tool plan based on category
#             tool_plan = _build_fallback_tool_plan(state)

#         # Execute planned tool calls sequentially
#         for tc in tool_plan:
#             tool_name = tc.get("tool_name") or tc.get("tool", "")
#             arguments = tc.get("arguments") or tc.get("args") or {}

#             result = await _execute_single_tool(tool_name, arguments, state)
#             step = f"Called {tool_name} → {_summarize_result(result)}"
#             state["reasoning_steps"].append(step)
#             logger.info(f"[{ticket_id}] {step}")

#             # Reduce confidence per error
#             if result is None or (isinstance(result, dict) and "error" in result):
#                 state["confidence"] = max(0.0, state["confidence"] - 0.05)

#         state["confidence_trace"].append(state["confidence"])

#     except Exception as e:
#         logger.error(f"[{ticket_id}] tool_execution exception: {e}")
#         state["errors"].append({
#             "tool": "tool_execution",
#             "error_type": type(e).__name__,
#             "message": str(e),
#             "timestamp": datetime.utcnow().isoformat() + "Z",
#         })

#     return {
#         "confidence": state["confidence"],
#         "confidence_trace": state["confidence_trace"],
#         "customer": state.get("customer"),
#         "order": state.get("order"),
#         "product": state.get("product"),
#         "kb_results": state.get("kb_results"),
#         "refund_issued": state.get("refund_issued", False),
#         "reply_message": state.get("reply_message"),
#         "escalation_summary": state.get("escalation_summary"),
#     }


# def _build_fallback_tool_plan(state: dict) -> list:
#     """Build a safe fallback tool plan when LLM fails."""
#     ticket = state["ticket"]
#     classification = state.get("classification") or {}
#     category = classification.get("category", "ambiguous")
#     order = state.get("order")
#     customer = state.get("customer")

#     plan = []
#     plan.append({
#         "tool_name": "search_knowledge_base",
#         "arguments": {"query": f"{category} policy"},
#         "reasoning": "Fallback: search KB for relevant policy",
#     })

#     if category in ("refund_request", "damaged_item"):
#         if order:
#             plan.append({
#                 "tool_name": "check_refund_eligibility",
#                 "arguments": {"order_id": order["order_id"]},
#                 "reasoning": "Check if refund is eligible",
#             })
#     elif category == "cancellation":
#         if order:
#             plan.append({
#                 "tool_name": "cancel_order",
#                 "arguments": {"order_id": order["order_id"]},
#                 "reasoning": "Attempt order cancellation",
#             })

#     plan.append({
#         "tool_name": "send_reply",
#         "arguments": {
#             "ticket_id": ticket.get("ticket_id", ""),
#             "message": (
#                 f"Hi {customer.get('name', 'there').split()[0] if customer else 'there'}, "
#                 "thank you for reaching out to ShopWave. We have received your request "
#                 "and a specialist will follow up shortly."
#             ),
#         },
#         "reasoning": "Fallback reply to customer",
#     })

#     return plan


# async def _execute_single_tool(tool_name: str, arguments: dict, state: dict):
#     """Execute a single tool by name with arguments."""
#     ticket_id = state["ticket"].get("ticket_id", "")
#     customer = state.get("customer")
#     order = state.get("order")

#     try:
#         if tool_name == "get_customer":
#             email = arguments.get("email") or state["ticket"].get("customer_email", "")
#             result = await get_customer(email, state)
#             if result:
#                 state["customer"] = result
#             return result

#         elif tool_name == "get_order":
#             oid = arguments.get("order_id") or state["ticket"].get("order_id", "")
#             result = await get_order(oid, state)
#             if result:
#                 state["order"] = result
#             return result

#         elif tool_name == "get_product":
#             pid = arguments.get("product_id") or (order.get("product_id") if order else None) or ""
#             result = await get_product(pid, state)
#             if result:
#                 state["product"] = result
#             return result

#         elif tool_name == "search_knowledge_base":
#             query = arguments.get("query", "return policy refund")
#             result = await search_knowledge_base(query, state)
#             state["kb_results"] = result
#             return result

#         elif tool_name == "check_refund_eligibility":
#             oid = arguments.get("order_id") or (order.get("order_id") if order else "")
#             result = await check_refund_eligibility(oid, state)
#             return result

#         elif tool_name == "issue_refund":
#             oid = arguments.get("order_id") or (order.get("order_id") if order else "")
#             amount = float(arguments.get("amount", order.get("amount", 0.0) if order else 0.0))
#             result = await issue_refund(oid, amount, state)
#             return result

#         elif tool_name == "send_reply":
#             msg = arguments.get("message", "")
#             result = await send_reply(ticket_id, msg, state)
#             return result

#         elif tool_name == "escalate":
#             summary = arguments.get("summary", arguments.get("summary_dict", {}))
#             priority = arguments.get("priority", "medium")
#             result = await escalate(ticket_id, summary, priority, state)
#             return result

#         elif tool_name == "cancel_order":
#             oid = arguments.get("order_id") or (order.get("order_id") if order else "")
#             result = await cancel_order(oid, state)
#             return result

#         else:
#             logger.warning(f"Unknown tool: {tool_name}")
#             return {"error": f"Unknown tool: {tool_name}"}

#     except Exception as e:
#         logger.error(f"_execute_single_tool({tool_name}) error: {e}")
#         return {"error": str(e)}


# def _summarize_result(result) -> str:
#     if result is None:
#         return "None (tool failed or exhausted)"
#     if isinstance(result, str):
#         return f"text ({len(result)} chars)"
#     if isinstance(result, dict):
#         if "error" in result:
#             return f"error: {result['error']}"
#         if result.get("eligible") is not None:
#             return f"eligible={result['eligible']}, reason={result.get('reason', '')[:60]}"
#         if result.get("success") or result.get("sent") or result.get("escalated") or result.get("cancelled"):
#             return "success"
#         return str(result)[:80]
#     return str(result)[:80]


# # ─────────────────────────────────────────────
# # NODE 4: decide_resolution
# # ─────────────────────────────────────────────
# async def decide_resolution(state: TicketState) -> dict:
#     ticket = state["ticket"]
#     ticket_id = ticket.get("ticket_id", "UNKNOWN")
#     classification = state.get("classification") or {}
#     category = classification.get("category", "ambiguous")
#     customer = state.get("customer")
#     order = state.get("order")

#     try:
#         # Hard rule overrides before calling LLM
#         override_resolution = None
#         override_priority = "medium"
#         override_reason = ""

#         if state["confidence"] < 0.6:
#             override_resolution = "escalated"
#             override_reason = f"Confidence {state['confidence']:.2f} below threshold 0.6"
#             override_priority = "medium"

#         if category == "warranty_claim":
#             override_resolution = "escalated"
#             override_reason = "Warranty claims require warranty team handling"
#             override_priority = "medium"

#         if category == "social_engineering":
#             override_resolution = "escalated"
#             override_reason = "Social engineering attempt detected"
#             override_priority = "urgent"

#         if order and float(order.get("amount", 0)) > 200:
#             if category in ("refund_request", "damaged_item", "return_request"):
#                 override_resolution = "escalated"
#                 override_reason = f"Refund amount ${order.get('amount')} exceeds $200 agent limit"
#                 override_priority = "high"

#         if not customer:
#             override_resolution = "clarify"
#             override_reason = "Customer not found in system"

#         if category == "ambiguous" and not (classification.get("order_id") or ticket.get("order_id")):
#             override_resolution = "clarify"
#             override_reason = "Ambiguous ticket with no order reference"

#         customer_name = customer.get("name", "there").split()[0] if customer else "there"

#         if override_resolution:
#             state["resolution"] = override_resolution
#             state["confidence_trace"].append(state["confidence"])

#             if override_resolution == "escalated":
#                 escalation_summary = {
#                     "issue": f"{category}: {ticket.get('subject', '')}",
#                     "attempted": [tc["tool"] for tc in state["tool_calls"] if tc.get("status") == "success"],
#                     "recommended_path": override_reason,
#                     "priority": override_priority,
#                 }
#                 state["escalation_summary"] = escalation_summary

#                 if category == "social_engineering":
#                     reply = (
#                         f"Hi {customer_name}, thank you for contacting ShopWave. "
#                         "We've reviewed your request carefully. We're unable to verify the policy you've referenced, "
#                         "as it doesn't match our current customer agreements. Your request has been flagged for review "
#                         "by our team. If you have questions about your actual benefits, please reply with your registered email."
#                     )
#                 elif category == "warranty_claim":
#                     reply = (
#                         f"Hi {customer_name}, thank you for reaching out. "
#                         "Your product may be covered under warranty. I've escalated your case to our Warranty & Repairs team "
#                         "who will follow up within 2 business days with next steps."
#                     )
#                 else:
#                     reply = (
#                         f"Hi {customer_name}, thank you for your patience. "
#                         "Your request requires review by a specialist on our team. "
#                         "We've escalated your ticket with priority and will follow up shortly. "
#                         "We appreciate your understanding."
#                     )
#             else:  # clarify
#                 if not customer:
#                     reply = (
#                         f"Hi there, thank you for contacting ShopWave. "
#                         "We were unable to locate an account with the email address provided. "
#                         "Could you please confirm the email address registered with your ShopWave account, "
#                         "along with your order number? This will help us assist you promptly."
#                     )
#                 else:
#                     reply = (
#                         f"Hi {customer_name}, thank you for reaching out to ShopWave. "
#                         "We'd love to help but need a bit more information. "
#                         "Could you please share your order number and a description of the issue? "
#                         "This will help us resolve things quickly for you."
#                     )

#             state["reply_message"] = reply
#             state["reasoning_steps"].append(
#                 f"Resolution override → {override_resolution} ({override_reason})"
#             )
#             logger.info(f"[{ticket_id}] Override resolution: {override_resolution} — {override_reason}")

#             return {
#                 "resolution": state["resolution"],
#                 "reply_message": state["reply_message"],
#                 "escalation_summary": state.get("escalation_summary"),
#                 "confidence": state["confidence"],
#                 "confidence_trace": state["confidence_trace"],
#             }

#         # Call Gemini for resolution decision
#         tool_results_summary = []
#         for tc in state["tool_calls"]:
#             if tc.get("status") == "success":
#                 tool_results_summary.append(f"- {tc['tool']}: {_summarize_result(tc.get('output'))}")

#         prompt = f"""You are a ShopWave senior support agent making the final resolution decision.

# TICKET:
# ID: {ticket.get('ticket_id')}
# Subject: {ticket.get('subject')}
# Body: {ticket.get('body')}

# CLASSIFICATION: {json.dumps(classification, indent=2)}
# CUSTOMER: {json.dumps(customer, indent=2) if customer else 'NOT FOUND'}
# ORDER: {json.dumps(order, indent=2) if order else 'NOT FOUND'}
# PRODUCT: {json.dumps(state.get('product'), indent=2) if state.get('product') else 'NOT FOUND'}
# CURRENT CONFIDENCE: {state['confidence']:.2f}

# TOOL RESULTS SO FAR:
# {chr(10).join(tool_results_summary) or 'No tools executed yet'}

# ERRORS ENCOUNTERED: {json.dumps(state.get('errors', []))}
# REFUND ALREADY ISSUED: {state.get('refund_issued', False)}

# Based on all context, decide the resolution. Return ONLY valid JSON:
# {{
#   "action": "<resolve | escalate | clarify>",
#   "confidence": <float 0.0-1.0>,
#   "reply_message": "<empathetic customer-facing message, address customer by first name: {customer_name}>",
#   "escalation_summary": {{
#     "issue": "<brief issue description>",
#     "attempted": ["<tool1>", "<tool2>"],
#     "recommended_path": "<who should handle this>",
#     "priority": "<low | medium | high | urgent>"
#   }} or null,
#   "reasoning": "<one sentence explaining decision>"
# }}"""

#         parsed = await _gemini_call(prompt)

#         if parsed is None:
#             parsed = {
#                 "action": "escalated",
#                 "confidence": 0.3,
#                 "reply_message": f"Hi {customer_name}, your request is being reviewed by our specialist team who will follow up shortly.",
#                 "escalation_summary": {
#                     "issue": ticket.get("subject", ""),
#                     "attempted": [],
#                     "recommended_path": "LLM decision failed — manual review",
#                     "priority": "medium",
#                 },
#                 "reasoning": "LLM decision node failed, defaulting to escalation",
#             }
#             state["policy_flags"].append("llm_decision_failed")

#         action = parsed.get("action", "escalated")
#         if action == "resolve":
#             action = "resolved"

#         llm_confidence = float(parsed.get("confidence", state["confidence"]))
#         state["confidence"] = min(state["confidence"], llm_confidence)

#         if state["confidence"] < 0.6 and action != "clarify":
#             action = "escalated"
#             state["reasoning_steps"].append(f"Confidence {state['confidence']:.2f} below 0.6 — escalating")

#         state["resolution"] = action
#         state["reply_message"] = parsed.get("reply_message", "")
#         state["confidence_trace"].append(state["confidence"])

#         if parsed.get("escalation_summary"):
#             state["escalation_summary"] = parsed["escalation_summary"]

#         state["reasoning_steps"].append(
#             f"Resolution decided: {action} (confidence={state['confidence']:.2f}). {parsed.get('reasoning', '')}"
#         )
#         logger.info(f"[{ticket_id}] Resolution: {action}, confidence={state['confidence']:.2f}")

#     except Exception as e:
#         logger.error(f"[{ticket_id}] decide_resolution exception: {e}")
#         state["resolution"] = "escalated"
#         state["reply_message"] = "Hi there, your request is being escalated to our specialist team."
#         state["errors"].append({
#             "tool": "decide_resolution",
#             "error_type": type(e).__name__,
#             "message": str(e),
#             "timestamp": datetime.utcnow().isoformat() + "Z",
#         })

#     return {
#         "resolution": state["resolution"],
#         "reply_message": state.get("reply_message"),
#         "escalation_summary": state.get("escalation_summary"),
#         "confidence": state["confidence"],
#         "confidence_trace": state["confidence_trace"],
#     }


# # ─────────────────────────────────────────────
# # NODE 5: execute_resolution
# # ─────────────────────────────────────────────
# async def execute_resolution(state: TicketState) -> dict:
#     ticket = state["ticket"]
#     ticket_id = ticket.get("ticket_id", "UNKNOWN")
#     resolution = state.get("resolution", "escalated")
#     order = state.get("order")
#     customer = state.get("customer")

#     try:
#         if resolution == "resolved":
#             # Issue refund if eligible and not yet issued
#             eligibility_result = next(
#                 (
#                     tc.get("output")
#                     for tc in state["tool_calls"]
#                     if tc.get("tool") == "check_refund_eligibility" and tc.get("status") == "success"
#                 ),
#                 None,
#             )
#             if (
#                 eligibility_result
#                 and isinstance(eligibility_result, dict)
#                 and eligibility_result.get("eligible")
#                 and not state.get("refund_issued")
#                 and order
#             ):
#                 amount = eligibility_result.get("amount", float(order.get("amount", 0.0)))
#                 refund_result = await issue_refund(order["order_id"], amount, state)
#                 state["reasoning_steps"].append(
#                     f"Issued refund ${amount:.2f} → {'success' if refund_result and refund_result.get('success') else 'failed'}"
#                 )

#             # ── Bug 6 fix ──────────────────────────────────────────────────────
#             # The original code had an else-branch whose inner guard was always False
#             # (dead code).  The correct logic is: send reply if no send_reply tool
#             # call has been recorded yet in state["tool_calls"].
#             if not any(tc.get("tool") == "send_reply" for tc in state["tool_calls"]):
#                 reply = state.get("reply_message") or (
#                     f"Hi {customer.get('name', 'there').split()[0] if customer else 'there'}, "
#                     "your request has been processed. Thank you for shopping with ShopWave!"
#                 )
#                 await send_reply(ticket_id, reply, state)

#         elif resolution == "escalated":
#             summary = state.get("escalation_summary") or {
#                 "issue": ticket.get("subject", ""),
#                 "attempted": [tc["tool"] for tc in state["tool_calls"] if tc.get("status") == "success"],
#                 "recommended_path": "Senior agent review",
#                 "priority": "medium",
#             }
#             priority = summary.get("priority", "medium")
#             await escalate(ticket_id, summary, priority, state)

#             reply = state.get("reply_message") or (
#                 f"Hi {customer.get('name', 'there').split()[0] if customer else 'there'}, "
#                 "we've escalated your request to a specialist who will follow up with you shortly. "
#                 "Thank you for your patience."
#             )
#             await send_reply(ticket_id, reply, state)

#         elif resolution == "clarify":
#             reply = state.get("reply_message") or (
#                 f"Hi {customer.get('name', 'there').split()[0] if customer else 'there'}, "
#                 "we need a bit more information to help you. "
#                 "Could you please provide your order number and more details about your issue?"
#             )
#             await send_reply(ticket_id, reply, state)

#         state["reasoning_steps"].append(f"Resolution executed: {resolution}")

#     except Exception as e:
#         logger.error(f"[{ticket_id}] execute_resolution exception: {e}")
#         state["errors"].append({
#             "tool": "execute_resolution",
#             "error_type": type(e).__name__,
#             "message": str(e),
#             "timestamp": datetime.utcnow().isoformat() + "Z",
#         })

#     return {
#         "reply_message": state.get("reply_message"),
#         "escalation_summary": state.get("escalation_summary"),
#         "refund_issued": state.get("refund_issued", False),
#     }


# # ─────────────────────────────────────────────
# # NODE 6: audit_logger
# # ─────────────────────────────────────────────
# async def audit_logger(state: TicketState) -> dict:
#     import time
#     ticket = state["ticket"]
#     ticket_id = ticket.get("ticket_id", "UNKNOWN")

#     processing_time_ms = int((time.time() - state.get("processing_start_time", time.time())) * 1000)

#     escalated = state.get("resolution") == "escalated"
#     reply_sent = any(tc.get("tool") == "send_reply" and tc.get("status") == "success" for tc in state["tool_calls"])

#     audit_entry = {
#         "ticket_id": ticket_id,
#         "timestamp": datetime.utcnow().isoformat() + "Z",
#         "processing_time_ms": processing_time_ms,
#         "customer_email": ticket.get("customer_email", ""),
#         "customer_tier": state.get("customer", {}).get("tier", "unknown") if state.get("customer") else "not_found",
#         "classification": state.get("classification"),
#         "confidence_trace": state.get("confidence_trace", []),
#         "tool_calls": state.get("tool_calls", []),
#         "tool_calls_count": len(state.get("tool_calls", [])),
#         "reasoning_steps": state.get("reasoning_steps", []),
#         "resolution": state.get("resolution", "unknown"),
#         "reply_sent": reply_sent,
#         "reply_message": state.get("reply_message"),
#         "escalated": escalated,
#         "escalation_summary": state.get("escalation_summary"),
#         "errors_encountered": state.get("errors", []),
#         "policy_flags": state.get("policy_flags", []),
#         "refund_issued": state.get("refund_issued", False),
#     }

#     state["audit_entry"] = audit_entry
#     logger.info(
#         f"[{ticket_id}] Audit logged: {state.get('resolution')} | "
#         f"tools={len(state['tool_calls'])} | errors={len(state.get('errors', []))}"
#     )

#     return {"audit_entry": audit_entry}


import os
import json
import logging
import asyncio
import re
from datetime import datetime, timezone
from typing import Optional

from google import genai
from google.genai import types as genai_types

from agent.state import TicketState
from tools.lookup import get_customer, get_order, get_product, get_orders_for_customer
from tools.knowledge import search_knowledge_base
from tools.actions import (
    check_refund_eligibility,
    issue_refund,
    send_reply,
    escalate,
    cancel_order,
)

logger = logging.getLogger(__name__)

# Configure Gemini — new google-genai SDK
_api_key = os.getenv("GEMINI_API_KEY", "")
_client = genai.Client(api_key=_api_key) if _api_key else None

GEMINI_MODEL = "gemini-2.5-flash"

# Categories where it makes sense to auto-look up most-recent order when none is provided.
# Ambiguous and policy_question tickets should NOT get a random order silently attached.
_ORDER_LOOKUP_CATEGORIES = {
    "refund_request",
    "return_request",
    "order_status",
    "cancellation",
    "warranty_claim",
    "damaged_item",
    "wrong_item",
}

# Tools allowed during pre-decision planning only (fact-finding / safe checks)
_SAFE_PRE_DECISION_TOOLS = {
    "get_customer",
    "get_order",
    "get_product",
    "search_knowledge_base",
    "check_refund_eligibility",
    "cancel_order",
}


def _normalize_resolution(value: Optional[str]) -> str:
    if not value:
        return "clarify"
    v = str(value).strip().lower()
    if v in {"resolved", "resolve"}:
        return "resolved"
    if v in {"escalated", "escalate"}:
        return "escalated"
    if v in {"clarify", "needs_clarification", "clarification"}:
        return "clarify"
    return "clarify"


def _extract_json(text: str) -> Optional[dict]:
    """Extract JSON from LLM response, handling markdown fences."""
    text = text.strip()
    # Strip markdown fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find first { ... } block
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


async def _gemini_call(prompt: str, retry: bool = True):
    """Call Gemini and return parsed JSON (dict or list). Returns None on failure."""
    if _client is None:
        logger.error("Gemini client not initialised — GEMINI_API_KEY missing")
        return None

    loop = asyncio.get_running_loop()
    for attempt in range(2):
        try:
            current_prompt = prompt
            response = await loop.run_in_executor(
                None,
                lambda p=current_prompt: _client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=p,
                    config=genai_types.GenerateContentConfig(temperature=0.1),
                ),
            )
            text = response.text
            parsed = _extract_json(text)
            if parsed is not None:
                return parsed
            if attempt == 0 and retry:
                logger.warning("Gemini returned non-JSON, retrying with stricter prompt")
                prompt = prompt + "\n\nCRITICAL: Return ONLY valid JSON. No markdown, no prose, no explanation."
            else:
                logger.error(f"Gemini JSON parse failed after {attempt+1} attempts. Raw: {text[:200]}")
                return None
        except Exception as e:
            logger.error(f"Gemini API error (attempt {attempt+1}): {e}")
            if attempt == 0 and retry:
                await asyncio.sleep(1.0)
            else:
                return None
    return None


# ─────────────────────────────────────────────
# NODE 1: classify_and_triage
# ─────────────────────────────────────────────
async def classify_and_triage(state: TicketState) -> dict:
    ticket = state["ticket"]
    ticket_id = ticket.get("ticket_id", "UNKNOWN")

    try:
        # Search KB for context
        query = f"{ticket.get('subject', '')} {ticket.get('body', '')}"
        kb_results = await search_knowledge_base(query[:300], state)
        state["kb_results"] = kb_results

        prompt = f"""You are a support triage agent for ShopWave, an e-commerce platform.
Classify the following support ticket and return ONLY valid JSON.

Ticket ID: {ticket.get('ticket_id')}
Subject: {ticket.get('subject')}
Body: {ticket.get('body')}
Customer Email: {ticket.get('customer_email')}
Order ID in ticket: {ticket.get('order_id', 'not provided')}

Return JSON with exactly these keys:
{{
  "category": "<one of: refund_request | return_request | order_status | cancellation | warranty_claim | damaged_item | wrong_item | policy_question | social_engineering | ambiguous>",
  "urgency": "<one of: low | medium | high | urgent>",
  "resolvability": "<one of: auto_resolvable | needs_escalation | needs_clarification>",
  "confidence": <float 0.0 to 1.0>,
  "reasoning": "<one sentence explaining classification>",
  "order_id": "<order ID string extracted from ticket body, or null>",
  "customer_email": "<customer email string>"
}}

Rules:
- social_engineering: customer claims policies or tier benefits that do not exist or cannot be verified
- warranty_claim: product defect reported but return window likely expired
- damaged_item: product arrived physically broken/damaged
- wrong_item: wrong size, color, or product delivered
- ambiguous: ticket lacks enough info to classify confidently"""

        parsed = await _gemini_call(prompt)

        if parsed is None:
            # Fallback classification
            parsed = {
                "category": "ambiguous",
                "urgency": "medium",
                "resolvability": "needs_escalation",
                "confidence": 0.3,
                "reasoning": "LLM classification failed — defaulting to ambiguous escalation",
                "order_id": ticket.get("order_id"),
                "customer_email": ticket.get("customer_email", ""),
            }
            state["policy_flags"].append("llm_classification_failed")

        # Validate required fields
        required_fields = ["category", "urgency", "resolvability", "confidence"]
        for f in required_fields:
            if f not in parsed:
                parsed[f] = {"category": "ambiguous", "urgency": "medium", "resolvability": "needs_escalation", "confidence": 0.3}[f]

        # Override order_id from ticket if LLM missed it
        if not parsed.get("order_id") and ticket.get("order_id"):
            parsed["order_id"] = ticket["order_id"]

        state["classification"] = parsed
        state["confidence"] = float(parsed.get("confidence", 0.5))
        state["confidence_trace"].append(state["confidence"])

        step = f"Classified as {parsed.get('category')} with {parsed.get('urgency')} urgency. Confidence: {state['confidence']:.2f}"
        state["reasoning_steps"].append(step)
        logger.info(f"[{ticket_id}] {step}")

    except Exception as e:
        logger.error(f"[{ticket_id}] classify_and_triage exception: {e}")
        state["classification"] = {
            "category": "ambiguous",
            "urgency": "medium",
            "resolvability": "needs_escalation",
            "confidence": 0.3,
            "reasoning": f"Node exception: {str(e)}",
            "order_id": ticket.get("order_id"),
            "customer_email": ticket.get("customer_email", ""),
        }
        state["confidence"] = 0.3
        state["confidence_trace"].append(0.3)
        state["errors"].append({
            "tool": "classify_and_triage",
            "error_type": type(e).__name__,
            "message": str(e),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    return {
        "classification": state["classification"],
        "confidence": state["confidence"],
        "confidence_trace": state["confidence_trace"],
        "kb_results": state.get("kb_results"),
    }


# ─────────────────────────────────────────────
# NODE 2: fetch_context
# ─────────────────────────────────────────────
async def fetch_context(state: TicketState) -> dict:
    ticket = state["ticket"]
    classification = state.get("classification") or {}
    ticket_id = ticket.get("ticket_id", "UNKNOWN")

    try:
        customer_email = classification.get("customer_email") or ticket.get("customer_email", "")
        order_id = classification.get("order_id") or ticket.get("order_id")

        # Run customer and order fetches concurrently
        tasks = [get_customer(customer_email, state)]
        if order_id:
            tasks.append(get_order(order_id, state))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        customer = results[0] if not isinstance(results[0], Exception) else None
        order = None
        if len(results) > 1:
            order = results[1] if not isinstance(results[1], Exception) else None

        # ── Bug 5 fix ──────────────────────────────────────────────────────────
        # Only fall back to "most-recent order" when:
        #   (a) no order_id was provided in the ticket, AND
        #   (b) the ticket category is one that genuinely involves an order
        #       (not ambiguous, policy_question, or social_engineering).
        # This prevents TKT-020 (ambiguous, no order) from silently attaching a
        # random order and drifting into an unintended refund path.
        category = classification.get("category", "ambiguous")
        if not order and not order_id and customer and category in _ORDER_LOOKUP_CATEGORIES:
            customer_orders = get_orders_for_customer(customer["customer_id"])
            if customer_orders:
                # Take the most recent order
                latest = sorted(customer_orders, key=lambda o: o.get("order_date", ""), reverse=True)[0]
                order = await get_order(latest["order_id"], state)
                if order:
                    state["reasoning_steps"].append(
                        f"No order_id in ticket — resolved most-recent order {order['order_id']} for category={category}"
                    )

        # Fetch product if order is available
        product = None
        if order and order.get("product_id"):
            product = await get_product(order["product_id"], state)

        # Adjust confidence based on missing context
        confidence = state["confidence"]
        if not customer:
            confidence = max(0.0, confidence - 0.1)
            state["reasoning_steps"].append("Customer not found in system — confidence reduced")
        if order_id and not order:
            confidence = max(0.0, confidence - 0.1)
            state["reasoning_steps"].append("Order not found in system — confidence reduced")

        state["customer"] = customer
        state["order"] = order
        state["product"] = product
        state["confidence"] = confidence
        state["confidence_trace"].append(confidence)

        customer_tier = customer.get("tier", "unknown") if customer else "not found"
        order_status = order.get("status", "unknown") if order else "not found"
        product_name = product.get("name", "unknown") if product else "not found"

        step = f"Fetched context: customer={customer_tier}, order={order_status}, product={product_name}"
        state["reasoning_steps"].append(step)
        logger.info(f"[{ticket_id}] {step}")

    except Exception as e:
        logger.error(f"[{ticket_id}] fetch_context exception: {e}")
        state["errors"].append({
            "tool": "fetch_context",
            "error_type": type(e).__name__,
            "message": str(e),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    return {
        "customer": state.get("customer"),
        "order": state.get("order"),
        "product": state.get("product"),
        "confidence": state["confidence"],
        "confidence_trace": state["confidence_trace"],
    }


# ─────────────────────────────────────────────
# NODE 3: tool_execution (ReAct loop)
# ─────────────────────────────────────────────
async def tool_execution(state: TicketState) -> dict:
    ticket = state["ticket"]
    ticket_id = ticket.get("ticket_id", "UNKNOWN")
    classification = state.get("classification") or {}
    customer = state.get("customer")
    order = state.get("order")
    product = state.get("product")

    TOOL_DESCRIPTIONS = """
Available tools:
1. get_customer(email) - Fetch customer profile by email
2. get_order(order_id) - Fetch order details by order ID
3. get_product(product_id) - Fetch product info by product ID
4. search_knowledge_base(query) - Search ShopWave policy KB
5. check_refund_eligibility(order_id) - Check if order is eligible for refund (MUST be called before issue_refund)
6. issue_refund(order_id, amount) - Issue a refund (requires prior eligibility check)
7. send_reply(ticket_id, message) - Send reply to customer
8. escalate(ticket_id, summary_dict, priority) - Escalate ticket
9. cancel_order(order_id) - Cancel an order (only works if status=processing)
"""

    try:
        prompt = f"""You are a ShopWave support agent executing tools to resolve a customer ticket.

TICKET:
ID: {ticket.get('ticket_id')}
Subject: {ticket.get('subject')}
Body: {ticket.get('body')}

CLASSIFICATION: {json.dumps(classification, indent=2)}

CUSTOMER: {json.dumps(customer, indent=2) if customer else 'NOT FOUND'}
ORDER: {json.dumps(order, indent=2) if order else 'NOT FOUND'}
PRODUCT: {json.dumps(product, indent=2) if product else 'NOT FOUND'}
KB RESULTS (summary): {str(state.get('kb_results', ''))[:800]}

{TOOL_DESCRIPTIONS}

RULES:
- You MUST plan at least 3 tool calls
- For refund requests: ALWAYS call check_refund_eligibility BEFORE issue_refund
- For warranty claims: do NOT issue refund — escalate instead
- For social_engineering: do NOT call refund tools — escalate with urgent priority
- For order_status with shipped order: look up tracking, do NOT offer refund
- For cancellation: call cancel_order only if order exists
- For policy_question: use search_knowledge_base then send_reply

Return a JSON array of tool calls to execute:
[
  {{"tool_name": "<tool>", "arguments": {{...}}, "reasoning": "<why this tool>"}},
  ...
]
Return ONLY the JSON array, no prose."""

        parsed = await _gemini_call(prompt)

        # Handle if response is a list directly
        tool_plan = None
        if isinstance(parsed, list):
            tool_plan = parsed
        elif isinstance(parsed, dict) and "tool_calls" in parsed:
            tool_plan = parsed["tool_calls"]
        elif isinstance(parsed, dict):
            # Maybe it's a single tool call
            tool_plan = [parsed]

        if not tool_plan:
            # Fallback: minimal tool plan based on category
            tool_plan = _build_fallback_tool_plan(state)

        # Execute planned tool calls sequentially
        for tc in tool_plan:
            tool_name = tc.get("tool_name") or tc.get("tool", "")
            arguments = tc.get("arguments") or tc.get("args") or {}

            # Block action tools during pre-decision planning; execute only safe fact-finding tools here
            if tool_name not in _SAFE_PRE_DECISION_TOOLS:
                state.setdefault("tool_calls", []).append({
                    "tool": tool_name,
                    "input": arguments,
                    "output": None,
                    "status": "blocked",
                    "attempt": 1,
                    "duration_ms": 0,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                })
                step = f"Skipped {tool_name} during pre-decision phase (deferred to execute_resolution)"
                state["reasoning_steps"].append(step)
                logger.info(f"[{ticket_id}] {step}")
                continue

            result = await _execute_single_tool(tool_name, arguments, state)
            step = f"Called {tool_name} → {_summarize_result(result)}"
            state["reasoning_steps"].append(step)
            logger.info(f"[{ticket_id}] {step}")

            # Reduce confidence per error
            if result is None or (isinstance(result, dict) and "error" in result):
                state["confidence"] = max(0.0, state["confidence"] - 0.05)

        state["confidence_trace"].append(state["confidence"])

    except Exception as e:
        logger.error(f"[{ticket_id}] tool_execution exception: {e}")
        state["errors"].append({
            "tool": "tool_execution",
            "error_type": type(e).__name__,
            "message": str(e),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    return {
        "confidence": state["confidence"],
        "confidence_trace": state["confidence_trace"],
        "customer": state.get("customer"),
        "order": state.get("order"),
        "product": state.get("product"),
        "kb_results": state.get("kb_results"),
        "refund_issued": state.get("refund_issued", False),
        "reply_message": state.get("reply_message"),
        "escalation_summary": state.get("escalation_summary"),
    }


def _build_fallback_tool_plan(state: dict) -> list:
    """Build a safe fallback tool plan when LLM fails."""
    ticket = state["ticket"]
    classification = state.get("classification") or {}
    category = classification.get("category", "ambiguous")
    order = state.get("order")
    customer = state.get("customer")

    plan = []
    plan.append({
        "tool_name": "search_knowledge_base",
        "arguments": {"query": f"{category} policy"},
        "reasoning": "Fallback: search KB for relevant policy",
    })

    if category in ("refund_request", "damaged_item"):
        if order:
            plan.append({
                "tool_name": "check_refund_eligibility",
                "arguments": {"order_id": order["order_id"]},
                "reasoning": "Check if refund is eligible",
            })
    elif category == "cancellation":
        if order:
            plan.append({
                "tool_name": "cancel_order",
                "arguments": {"order_id": order["order_id"]},
                "reasoning": "Attempt order cancellation",
            })

    plan.append({
        "tool_name": "send_reply",
        "arguments": {
            "ticket_id": ticket.get("ticket_id", ""),
            "message": (
                f"Hi {customer.get('name', 'there').split()[0] if customer else 'there'}, "
                "thank you for reaching out to ShopWave. We have received your request "
                "and a specialist will follow up shortly."
            ),
        },
        "reasoning": "Fallback reply to customer",
    })

    return plan


async def _execute_single_tool(tool_name: str, arguments: dict, state: dict):
    """Execute a single tool by name with arguments."""
    ticket_id = state["ticket"].get("ticket_id", "")
    customer = state.get("customer")
    order = state.get("order")

    try:
        if tool_name == "get_customer":
            email = arguments.get("email") or state["ticket"].get("customer_email", "")
            result = await get_customer(email, state)
            if result:
                state["customer"] = result
            return result

        elif tool_name == "get_order":
            oid = arguments.get("order_id") or state["ticket"].get("order_id", "")
            result = await get_order(oid, state)
            if result:
                state["order"] = result
            return result

        elif tool_name == "get_product":
            pid = arguments.get("product_id") or (order.get("product_id") if order else None) or ""
            result = await get_product(pid, state)
            if result:
                state["product"] = result
            return result

        elif tool_name == "search_knowledge_base":
            query = arguments.get("query", "return policy refund")
            result = await search_knowledge_base(query, state)
            state["kb_results"] = result
            return result

        elif tool_name == "check_refund_eligibility":
            oid = arguments.get("order_id") or (order.get("order_id") if order else "")
            result = await check_refund_eligibility(oid, state)
            return result

        elif tool_name == "issue_refund":
            oid = arguments.get("order_id") or (order.get("order_id") if order else "")
            amount = float(arguments.get("amount", order.get("amount", 0.0) if order else 0.0))
            result = await issue_refund(oid, amount, state)
            return result

        elif tool_name == "send_reply":
            msg = arguments.get("message", "")
            result = await send_reply(ticket_id, msg, state)
            return result

        elif tool_name == "escalate":
            summary = arguments.get("summary", arguments.get("summary_dict", {}))
            priority = arguments.get("priority", "medium")
            result = await escalate(ticket_id, summary, priority, state)
            return result

        elif tool_name == "cancel_order":
            oid = arguments.get("order_id") or (order.get("order_id") if order else "")
            result = await cancel_order(oid, state)
            return result

        else:
            logger.warning(f"Unknown tool: {tool_name}")
            return {"error": f"Unknown tool: {tool_name}"}

    except Exception as e:
        logger.error(f"_execute_single_tool({tool_name}) error: {e}")
        return {"error": str(e)}


def _summarize_result(result) -> str:
    if result is None:
        return "None (tool failed or exhausted)"
    if isinstance(result, str):
        return f"text ({len(result)} chars)"
    if isinstance(result, dict):
        if "error" in result:
            return f"error: {result['error']}"
        if result.get("eligible") is not None:
            return f"eligible={result['eligible']}, reason={result.get('reason', '')[:60]}"
        if result.get("success") or result.get("sent") or result.get("escalated") or result.get("cancelled"):
            return "success"
        return str(result)[:80]
    return str(result)[:80]


# ─────────────────────────────────────────────
# NODE 4: decide_resolution
# ─────────────────────────────────────────────
async def decide_resolution(state: TicketState) -> dict:
    ticket = state["ticket"]
    ticket_id = ticket.get("ticket_id", "UNKNOWN")
    classification = state.get("classification") or {}
    category = classification.get("category", "ambiguous")
    customer = state.get("customer")
    order = state.get("order")

    try:
        # Hard rule overrides before calling LLM
        override_resolution = None
        override_priority = "medium"
        override_reason = ""

        # IMPORTANT: use priority ordering so security tickets cannot be downgraded later
        if category == "social_engineering":
            override_resolution = "escalated"
            override_reason = "Social engineering attempt detected"
            override_priority = "urgent"
        elif category == "warranty_claim":
            override_resolution = "escalated"
            override_reason = "Warranty claims require warranty team handling"
            override_priority = "medium"
        elif state["confidence"] < 0.6:
            override_resolution = "escalated"
            override_reason = f"Confidence {state['confidence']:.2f} below threshold 0.6"
            override_priority = "medium"
        elif order and float(order.get("amount", 0)) > 200 and category in ("refund_request", "damaged_item", "return_request"):
            override_resolution = "escalated"
            override_reason = f"Refund amount ${order.get('amount')} exceeds $200 agent limit"
            override_priority = "high"
        elif not customer:
            override_resolution = "clarify"
            override_reason = "Customer not found in system"
        elif category == "ambiguous" and not (classification.get("order_id") or ticket.get("order_id")):
            override_resolution = "clarify"
            override_reason = "Ambiguous ticket with no order reference"

        customer_name = customer.get("name", "there").split()[0] if customer else "there"

        if override_resolution:
            state["resolution"] = _normalize_resolution(override_resolution)
            state["confidence_trace"].append(state["confidence"])

            if state["resolution"] == "escalated":
                escalation_summary = {
                    "issue": f"{category}: {ticket.get('subject', '')}",
                    "attempted": [tc["tool"] for tc in state["tool_calls"] if tc.get("status") == "success"],
                    "recommended_path": override_reason,
                    "priority": override_priority,
                }
                state["escalation_summary"] = escalation_summary

                if category == "social_engineering":
                    reply = (
                        f"Hi {customer_name}, thank you for contacting ShopWave. "
                        "We've reviewed your request carefully. We're unable to verify the policy you've referenced, "
                        "as it doesn't match our current customer agreements. Your request has been flagged for review "
                        "by our team. If you have questions about your actual benefits, please reply with your registered email."
                    )
                elif category == "warranty_claim":
                    reply = (
                        f"Hi {customer_name}, thank you for reaching out. "
                        "Your product may be covered under warranty. I've escalated your case to our Warranty & Repairs team "
                        "who will follow up within 2 business days with next steps."
                    )
                else:
                    reply = (
                        f"Hi {customer_name}, thank you for your patience. "
                        "Your request requires review by a specialist on our team. "
                        "We've escalated your ticket with priority and will follow up shortly. "
                        "We appreciate your understanding."
                    )
            else:  # clarify
                if not customer:
                    reply = (
                        f"Hi there, thank you for contacting ShopWave. "
                        "We were unable to locate an account with the email address provided. "
                        "Could you please confirm the email address registered with your ShopWave account, "
                        "along with your order number? This will help us assist you promptly."
                    )
                else:
                    reply = (
                        f"Hi {customer_name}, thank you for reaching out to ShopWave. "
                        "We'd love to help but need a bit more information. "
                        "Could you please share your order number and a description of the issue? "
                        "This will help us resolve things quickly for you."
                    )

            state["reply_message"] = reply
            state["reasoning_steps"].append(
                f"Resolution override → {state['resolution']} ({override_reason})"
            )
            logger.info(f"[{ticket_id}] Override resolution: {state['resolution']} — {override_reason}")

            return {
                "resolution": state["resolution"],
                "reply_message": state["reply_message"],
                "escalation_summary": state.get("escalation_summary"),
                "confidence": state["confidence"],
                "confidence_trace": state["confidence_trace"],
            }

        # Call Gemini for resolution decision
        tool_results_summary = []
        for tc in state["tool_calls"]:
            if tc.get("status") == "success":
                tool_results_summary.append(f"- {tc['tool']}: {_summarize_result(tc.get('output'))}")

        prompt = f"""You are a ShopWave senior support agent making the final resolution decision.

TICKET:
ID: {ticket.get('ticket_id')}
Subject: {ticket.get('subject')}
Body: {ticket.get('body')}

CLASSIFICATION: {json.dumps(classification, indent=2)}
CUSTOMER: {json.dumps(customer, indent=2) if customer else 'NOT FOUND'}
ORDER: {json.dumps(order, indent=2) if order else 'NOT FOUND'}
PRODUCT: {json.dumps(state.get('product'), indent=2) if state.get('product') else 'NOT FOUND'}
CURRENT CONFIDENCE: {state['confidence']:.2f}

TOOL RESULTS SO FAR:
{chr(10).join(tool_results_summary) or 'No tools executed yet'}

ERRORS ENCOUNTERED: {json.dumps(state.get('errors', []))}
REFUND ALREADY ISSUED: {state.get('refund_issued', False)}

Based on all context, decide the resolution. Return ONLY valid JSON:
{{
  "action": "<resolve | escalate | clarify>",
  "confidence": <float 0.0-1.0>,
  "reply_message": "<empathetic customer-facing message, address customer by first name: {customer_name}>",
  "escalation_summary": {{
    "issue": "<brief issue description>",
    "attempted": ["<tool1>", "<tool2>"],
    "recommended_path": "<who should handle this>",
    "priority": "<low | medium | high | urgent>"
  }} or null,
  "reasoning": "<one sentence explaining decision>"
}}"""

        parsed = await _gemini_call(prompt)

        if parsed is None:
            parsed = {
                "action": "escalated",
                "confidence": 0.3,
                "reply_message": f"Hi {customer_name}, your request is being reviewed by our specialist team who will follow up shortly.",
                "escalation_summary": {
                    "issue": ticket.get("subject", ""),
                    "attempted": [],
                    "recommended_path": "LLM decision failed — manual review",
                    "priority": "medium",
                },
                "reasoning": "LLM decision node failed, defaulting to escalation",
            }
            state["policy_flags"].append("llm_decision_failed")

        action = _normalize_resolution(parsed.get("action", "escalated"))

        llm_confidence = float(parsed.get("confidence", state["confidence"]))
        state["confidence"] = min(state["confidence"], llm_confidence)

        if state["confidence"] < 0.6 and action != "clarify":
            action = "escalated"
            state["reasoning_steps"].append(f"Confidence {state['confidence']:.2f} below 0.6 — escalating")

        state["resolution"] = _normalize_resolution(action)
        state["reply_message"] = parsed.get("reply_message", "")
        state["confidence_trace"].append(state["confidence"])

        if parsed.get("escalation_summary"):
            state["escalation_summary"] = parsed["escalation_summary"]

        state["reasoning_steps"].append(
            f"Resolution decided: {state['resolution']} (confidence={state['confidence']:.2f}). {parsed.get('reasoning', '')}"
        )
        logger.info(f"[{ticket_id}] Resolution: {state['resolution']}, confidence={state['confidence']:.2f}")

    except Exception as e:
        logger.error(f"[{ticket_id}] decide_resolution exception: {e}")
        state["resolution"] = "escalated"
        state["reply_message"] = "Hi there, your request is being escalated to our specialist team."
        state["errors"].append({
            "tool": "decide_resolution",
            "error_type": type(e).__name__,
            "message": str(e),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    return {
        "resolution": state["resolution"],
        "reply_message": state.get("reply_message"),
        "escalation_summary": state.get("escalation_summary"),
        "confidence": state["confidence"],
        "confidence_trace": state["confidence_trace"],
    }


# ─────────────────────────────────────────────
# NODE 5: execute_resolution
# ─────────────────────────────────────────────
async def execute_resolution(state: TicketState) -> dict:
    ticket = state["ticket"]
    ticket_id = ticket.get("ticket_id", "UNKNOWN")
    resolution = _normalize_resolution(state.get("resolution", "escalated"))
    state["resolution"] = resolution
    order = state.get("order")
    customer = state.get("customer")

    try:
        if resolution == "resolved":
            # Issue refund if eligible and not yet issued
            eligibility_result = next(
                (
                    tc.get("output")
                    for tc in state["tool_calls"]
                    if tc.get("tool") == "check_refund_eligibility" and tc.get("status") == "success"
                ),
                None,
            )
            if (
                eligibility_result
                and isinstance(eligibility_result, dict)
                and eligibility_result.get("eligible")
                and not state.get("refund_issued")
                and order
            ):
                amount = eligibility_result.get("amount", float(order.get("amount", 0.0)))
                refund_result = await issue_refund(order["order_id"], amount, state)
                state["reasoning_steps"].append(
                    f"Issued refund ${amount:.2f} → {'success' if refund_result and refund_result.get('success') else 'failed'}"
                )

            # ── Bug 6 fix ──────────────────────────────────────────────────────
            # The original code had an else-branch whose inner guard was always False
            # (dead code).  The correct logic is: send reply if no send_reply tool
            # call has been recorded yet in state["tool_calls"].
            if not any(tc.get("tool") == "send_reply" and tc.get("status") == "success" for tc in state["tool_calls"]):
                reply = state.get("reply_message") or (
                    f"Hi {customer.get('name', 'there').split()[0] if customer else 'there'}, "
                    "your request has been processed. Thank you for shopping with ShopWave!"
                )
                await send_reply(ticket_id, reply, state)

        elif resolution == "escalated":
            summary = state.get("escalation_summary") or {
                "issue": ticket.get("subject", ""),
                "attempted": [tc["tool"] for tc in state["tool_calls"] if tc.get("status") == "success"],
                "recommended_path": "Senior agent review",
                "priority": "medium",
            }
            priority = summary.get("priority", "medium")
            await escalate(ticket_id, summary, priority, state)

            reply = state.get("reply_message") or (
                f"Hi {customer.get('name', 'there').split()[0] if customer else 'there'}, "
                "we've escalated your request to a specialist who will follow up with you shortly. "
                "Thank you for your patience."
            )
            await send_reply(ticket_id, reply, state)

        elif resolution == "clarify":
            reply = state.get("reply_message") or (
                f"Hi {customer.get('name', 'there').split()[0] if customer else 'there'}, "
                "we need a bit more information to help you. "
                "Could you please provide your order number and more details about your issue?"
            )
            await send_reply(ticket_id, reply, state)

        state["reasoning_steps"].append(f"Resolution executed: {resolution}")

    except Exception as e:
        logger.error(f"[{ticket_id}] execute_resolution exception: {e}")
        state["errors"].append({
            "tool": "execute_resolution",
            "error_type": type(e).__name__,
            "message": str(e),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    return {
        "reply_message": state.get("reply_message"),
        "escalation_summary": state.get("escalation_summary"),
        "refund_issued": state.get("refund_issued", False),
    }


# ─────────────────────────────────────────────
# NODE 6: audit_logger
# ─────────────────────────────────────────────
async def audit_logger(state: TicketState) -> dict:
    import time
    ticket = state["ticket"]
    ticket_id = ticket.get("ticket_id", "UNKNOWN")

    processing_time_ms = int((time.time() - state.get("processing_start_time", time.time())) * 1000)

    state["resolution"] = _normalize_resolution(state.get("resolution", "unknown"))
    escalated = state.get("resolution") == "escalated"
    reply_sent = any(tc.get("tool") == "send_reply" and tc.get("status") == "success" for tc in state["tool_calls"])

    audit_entry = {
        "ticket_id": ticket_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "processing_time_ms": processing_time_ms,
        "customer_email": ticket.get("customer_email", ""),
        "customer_tier": state.get("customer", {}).get("tier", "unknown") if state.get("customer") else "not_found",
        "classification": state.get("classification"),
        "confidence_trace": state.get("confidence_trace", []),
        "tool_calls": state.get("tool_calls", []),
        "tool_calls_count": len(state.get("tool_calls", [])),
        "reasoning_steps": state.get("reasoning_steps", []),
        "resolution": state.get("resolution", "unknown"),
        "reply_sent": reply_sent,
        "reply_message": state.get("reply_message"),
        "escalated": escalated,
        "escalation_summary": state.get("escalation_summary"),
        "errors_encountered": state.get("errors", []),
        "policy_flags": state.get("policy_flags", []),
        "refund_issued": state.get("refund_issued", False),
    }

    state["audit_entry"] = audit_entry
    logger.info(
        f"[{ticket_id}] Audit logged: {state.get('resolution')} | "
        f"tools={len(state['tool_calls'])} | errors={len(state.get('errors', []))}"
    )

    return {"audit_entry": audit_entry}