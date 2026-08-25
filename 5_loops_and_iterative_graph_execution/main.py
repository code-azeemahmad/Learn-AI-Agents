from typing import Literal

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict


class State(TypedDict):
    count: int

def increment(state: State):
    return {
        "count": state["count"] + 1
    }

def route(state: State) -> Literal["increment", END]: # type: ignore
    if state["count"] < 3:
        return "increment"
    return END


builder = StateGraph(State)

builder.add_node("increment", increment)

builder.add_edge(START, "increment")

builder.add_conditional_edges(
    "increment",
    route,
)

graph = builder.compile()

result = graph.invoke(
    {
        "count": 0
    }
)

print(result)
print("-" * 99)

class RetryState(TypedDict):
    attempts: int 
    success: bool

def call_tool(state: RetryState):
    attempts = state["attempts"] + 1

    success = attempts >= 3

    return {
        "attempts": attempts,
        "success": success,
    }

def route(state: RetryState) -> Literal["call_tool", END]: # type: ignore
    if state["success"]:    # Success -> END
        return END

    if state["attempts"] >= 3:  # Maximum Attempts(safety limit) -> END
        return END

    return "call_tool"


graph = StateGraph(RetryState)

graph.add_node("call_tool", call_tool)
graph.add_edge(START, "call_tool")
graph.add_conditional_edges(
    "call_tool",
    route,
)

app = graph.compile()


result = app.invoke({
    "attempts": 0,
    "success": False,
})

print(result)