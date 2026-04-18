from typing import TypedDict, Optional, List, Any


class TicketState(TypedDict):
    ticket: dict
    customer: Optional[dict]
    order: Optional[dict]
    product: Optional[dict]
    kb_results: Optional[str]
    tool_calls: List[dict]
    reasoning_steps: List[str]
    classification: Optional[dict]
    confidence: float
    confidence_trace: List[float]
    resolution: Optional[str]
    reply_message: Optional[str]
    escalation_summary: Optional[dict]
    errors: List[dict]
    refund_issued: bool
    audit_entry: dict
    policy_flags: List[str]
    processing_start_time: float
