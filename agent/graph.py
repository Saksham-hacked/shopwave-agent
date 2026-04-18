from langgraph.graph import StateGraph, END

from agent.state import TicketState
from agent.nodes import (
    classify_and_triage,
    fetch_context,
    tool_execution,
    decide_resolution,
    execute_resolution,
    audit_logger,
)
from agent.router import route_after_classify, route_after_decide


def build_graph():
    graph = StateGraph(TicketState)

    # Add all nodes
    graph.add_node("classify_and_triage", classify_and_triage)
    graph.add_node("fetch_context", fetch_context)
    graph.add_node("tool_execution", tool_execution)
    graph.add_node("decide_resolution", decide_resolution)
    graph.add_node("execute_resolution", execute_resolution)
    graph.add_node("audit_logger", audit_logger)

    # Entry point
    graph.set_entry_point("classify_and_triage")

    # Conditional edge: social engineering skips fetch_context
    graph.add_conditional_edges(
        "classify_and_triage",
        route_after_classify,
        {
            "fetch_context": "fetch_context",
            "decide_resolution": "decide_resolution",
        },
    )

    # Linear edges
    graph.add_edge("fetch_context", "tool_execution")
    graph.add_edge("tool_execution", "decide_resolution")

    # All resolution types go to execute_resolution
    graph.add_conditional_edges(
        "decide_resolution",
        route_after_decide,
        {
            "execute_resolution": "execute_resolution",
        },
    )

    graph.add_edge("execute_resolution", "audit_logger")
    graph.add_edge("audit_logger", END)

    return graph.compile()


# Compiled app — imported by main.py
app = build_graph()
