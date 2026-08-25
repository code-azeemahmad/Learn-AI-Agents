from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict


class State(TypedDict):
    count: int

builder = StateGraph(State)

def increment(state: State):
    return {
        "count": state["count"] + 1
    }

builder.add_node("increment", increment)

builder.add_edge(START, "increment")
builder.add_edge("increment", END)

checkpointer = InMemorySaver()

graph = builder.compile(
    checkpointer=checkpointer
)

config1 = {
    "configurable": {
        "thread_id": "123"
    }
}

config2 = {
    "configurable": {
        "thread_id": "456"
    }
}

result = graph.invoke(
    {
        "count": 0,
    },
    config=config1
)
print(result)