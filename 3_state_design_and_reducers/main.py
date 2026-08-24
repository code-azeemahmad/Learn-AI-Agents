import operator
from typing import Annotated

from langgraph.graph import END, START, MessagesState, StateGraph, add_messages
from langgraph.graph.message import AnyMessage
from typing_extensions import TypedDict


class State(MessagesState):
    messages: Annotated[list[AnyMessage], add_messages]


def first_message(state: State):
    return {
        "messages": ["Hello,"]
    }

def second_message(state: State):
    return {
        "messages": ["How are you?"]
    }

builder = StateGraph(State)

builder.add_node("first_message", first_message)
builder.add_node("second_message", second_message)

builder.add_edge(START, "first_message")
builder.add_edge("first_message", "second_message")
builder.add_edge("second_message", END)

graph = builder.compile()

result = graph.invoke(
    {
        "messages": [],
    }
)

print(result)

# 1. State with a Reducer
class State(TypedDict):
    name: str # Default behavior: Overwrite
    logs: Annotated[list[str], operator.add] # Reducer behavior: Append/Add

# 2. Nodes returning partial updates
def node_1(state: State):
    # We only return the NEW log. The framework appends it.
    return {"name": "Alice", "logs": ["Node 1 executed."]}

def node_2(state: State):
    # We only return the NEW log. 
    return {"name": "Bob", "logs": ["Node 2 executed."]}

# 3. Build & Compile
builder = StateGraph(State)
builder.add_node("n1", node_1)
builder.add_node("n2", node_2)
builder.add_edge(START, "n1")
builder.add_edge("n1", "n2")
builder.add_edge("n2", END)

graph = builder.compile()

# Notice our initial state
final_state = graph.invoke({"name": "Initial", "logs": ["Started graph."]})
print(final_state)
# Output: 
# {'name': 'Bob', 'logs': ['Started graph.', 'Node 1 executed.', 'Node 2 executed.']}
