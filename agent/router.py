from agent.state import TicketState


def route_after_classify(state: TicketState) -> str:
    """After classification, route social engineering directly to decide_resolution."""
    classification = state.get("classification") or {}
    category = classification.get("category", "ambiguous")
    if category == "social_engineering":
        return "decide_resolution"
    return "fetch_context"


def route_after_decide(state: TicketState) -> str:
    """All resolution paths converge at execute_resolution."""
    # All paths go to execute_resolution regardless of resolved/escalated/clarify
    return "execute_resolution"
