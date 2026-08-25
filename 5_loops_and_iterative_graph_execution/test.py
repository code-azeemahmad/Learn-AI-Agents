from typing import Literal

from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict


class State(TypedDict):
    success: bool
    attempts: int

def tool_call(state: State):
    attempts = state["attempts"] + 1
    success = attempts >= 3

    return {
        "attempts": attempts,
        "success": success
    }

def route(state: State) -> Literal[END, "tool_call"]: # type: ignore
    if state["success"]:
        return END

    if state["attempts"] >= 3:
        return END

    return "tool_call"

graph = StateGraph(State)

graph.add_node("tool_call", tool_call)
graph.add_edge(START, "tool_call")
graph.add_conditional_edges(
    "tool_call",
    route,
)

app = graph.compile()

try:
    result = app.invoke(
    {
        "success": False,
        "attempts": 0,
    },
    {"recursion_limit": 2}
    )
    
    print(result)

except GraphRecursionError as e:
    print(f"  [Framework] GraphRecursionError caught! The framework killed the infinite loop.")  # noqa: F541
    print(f"  [Framework Error Details]: {e}")