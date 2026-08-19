"""LangGraph assembly: fan-out reviewers → critic."""

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from .state import AgentState
from .nodes import run_reviewer, critique

REVIEWER_TYPES = ["security", "performance", "logic", "style"]


def _dispatch_reviewers(state: AgentState) -> list[Send]:
    """Fan-out: send the diff to all four reviewers in parallel."""
    return [
        Send("run_reviewer", {**state, "reviewer_type": rt})
        for rt in REVIEWER_TYPES
    ]


def build_graph():
    builder = StateGraph(AgentState)

    builder.add_node("run_reviewer", run_reviewer)
    builder.add_node("critique", critique)

    # START → fan-out to 4 parallel reviewer nodes
    builder.add_conditional_edges(START, _dispatch_reviewers, ["run_reviewer"])
    # All reviewer nodes fan-in → critique → END
    builder.add_edge("run_reviewer", "critique")
    builder.add_edge("critique", END)

    return builder.compile()


graph = build_graph()
