# Failure Mode Analysis

## 1. Tool Timeout (check_refund_eligibility)
**Scenario**: check_refund_eligibility times out (20% rate in demo mode)
**Detection**: asyncio.TimeoutError caught in call_with_retry
**Response**: Exponential backoff retry (3 attempts: 0.3s, 0.6s, 1.2s)
**If exhausted**: Logged to dead_letter, confidence reduced by 0.1,
ticket escalated with summary "Could not verify refund eligibility — manual review needed"
**Never crashes**: Returns None, caller handles gracefully

## 2. Malformed Tool Response
**Scenario**: get_order returns invalid JSON fragment
**Detection**: {"__malformed__": True} sentinel injected, ValueError raised
**Response**: Retry up to 3 times; if still malformed, treat as tool failure
**If exhausted**: State["order"] = None, agent proceeds with available context,
confidence reduced, escalation triggered if order data was critical

## 3. LLM Returns Invalid JSON
**Scenario**: Gemini returns prose instead of JSON for classification or decision node
**Detection**: json.JSONDecodeError caught in all Gemini response parsers
**Response**: Retry the LLM call once with a stricter "return ONLY valid JSON" prompt
**If second attempt fails**: Fallback classification applied
(category="ambiguous", resolvability="needs_escalation", confidence=0.3),
ticket automatically escalated with note "LLM classification failed"

## 4. Customer Not Found (TKT-016)
**Scenario**: Email unknown.user@email.com not in customers database
**Detection**: get_customer returns None
**Response**: Resolution set to "clarify", confidence dropped to 0.4,
send_reply asks customer to provide registered email and order number
**No crash, no refund attempted**

## 5. Social Engineering Attempt (TKT-018)
**Scenario**: Customer falsely claims premium tier for instant refund policy that doesn't exist
**Detection**: Classification node identifies social_engineering category
**Response**: Pre-routed to escalation BEFORE any tool calls, priority="urgent",
professional reply sent explaining no such policy exists,
customer tier verified via get_customer (standard, not premium), flagged in audit

## 6. Refund Tool Called Without Eligibility Check
**Scenario**: Agent tries to call issue_refund before check_refund_eligibility
**Detection**: Guard in issue_refund scans state["tool_calls"] for prior eligibility check
**Response**: Returns error {eligible_check_missing: true}, tool_execution node
retries with correct order, logs the guard violation in audit_entry["policy_flags"]
