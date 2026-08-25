import re
from typing import Literal

from langgraph.graph import END, START, MessagesState, StateGraph
from typing_extensions import TypedDict


class State(MessagesState):
    user_input: str
    intent: str
    result: str

def classify(state: State):
    if "search" in state["user_input"].lower():
        return {"intent": "search"}
    
    return {"intent": "direct"}


def search_node(state: State):
    return {
        "result": f"Searching for: {state['user_input']}"
    }

def direct_node(state: State):
    return {
        "result": f"Answering directly: {state['user_input']}"
    }

def route(state: State) -> Literal["search", "direct"]:
    return state["intent"]

builder = StateGraph(State)

builder.add_node("classify", classify)
builder.add_node("search_node", search_node)
builder.add_node("direct_node", direct_node)

builder.add_edge(START, "classify")

builder.add_conditional_edges(
    "classify",
    route,
    {
        "search": "search_node",
        "direct": "direct_node",
    },
)

builder.add_edge("search_node", END)
builder.add_edge("direct_node", END)

graph = builder.compile()

answer = graph.invoke(
    {
        "user_input": "direct for LangGraph documentation",
        "intent": "",
        "result": "",
    }
)

print(answer)


# 1. State Schema
class State(TypedDict):
    user_input: str
    intent: str
    result: str

# 2. Worker Nodes
def classify(state: State):
    query = state["user_input"]
    # Check if any math operators exist in the string
    if any(op in query for op in ["+", "-", "*", "/"]):
        return {"intent": "calculate"}
    else:
        return {"intent": "direct"}

def calculate_node(state: State):
    query = state["user_input"]
    try:
        # Extract only the math expression using simple regex for safety
        expression = re.sub(r'[^0-9+\-*/. ]', '', query).strip()
        answer = eval(expression)
        return {"result": f"Calculated Answer: {answer}"}
    except Exception as e:  # noqa: BLE001
        return {"result": f"Calculation Error: {e}"}

def direct_node(state: State):
    return {"result": "I don't need a calculator for this. Answering directly."}

# 3. The Router Function
def route(state: State) -> Literal["calculate", "direct"]:
    # The router reads the state and returns exactly one of the permitted literal strings
    if state["intent"] == "calculate":
        return "calculate"
    return "direct"

# 4. Build the Graph
builder = StateGraph(State)

builder.add_node("classify", classify)
builder.add_node("calculate_node", calculate_node)
builder.add_node("direct_node", direct_node)

# Start always goes to classify
builder.add_edge(START, "classify")

# The brain of the graph: Conditional Routing
builder.add_conditional_edges(
    "classify",  # Source node
    route,       # The router function
    {            # The map: Router output -> Next Node
        "calculate": "calculate_node",
        "direct": "direct_node",
    }
)

# Both leaf nodes go to END
builder.add_edge("calculate_node", END)
builder.add_edge("direct_node", END)

# Compile into executable
graph = builder.compile()

# --- 5. Execution & Testing ---

print("--- Test 1: Math Query ---")
result_math = graph.invoke({
    "user_input": "What is 15 * 4?",
    "intent": "",
    "result": ""
})
print(result_math)

print("\n--- Test 2: General Query ---")
result_general = graph.invoke({
    "user_input": "What is LangGraph?",
    "intent": "",
    "result": ""
})
print(result_general)