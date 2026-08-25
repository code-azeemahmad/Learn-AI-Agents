from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict


class State(TypedDict):
    name: str
    message: str

def greet(state: State) -> State:
    return {
        "message": f"Hello, {state['name'].upper()}!"
    }

def prepare(state: State):
    return {
        "name": state["name"].strip()
    }
    

builder = StateGraph(State)
builder.add_node("prepare", prepare)
builder.add_node("greet", greet)

builder.add_edge(START, "prepare")
builder.add_edge("prepare", "greet")
builder.add_edge("greet", END)

graph = builder.compile()

result = graph.invoke(
    {
        "name": "    azeem      ",
    }
)

print(result)
print("-" * 99)
# 1. Define the State Schema
class GraphState(TypedDict):
    message: str
    step_count: int

# 2. Define the Nodes (Just standard Python functions)
def node_a(state: GraphState):
    print(f"--- Entering Node A | Current state: {state} ---")
    # We return a dict containing ONLY the keys we want to update
    return {
        "message": state["message"] + " -> Processed by A", 
        "step_count": state["step_count"] + 1
    }

def node_b(state: GraphState):
    print(f"--- Entering Node B | Current state: {state} ---")
    return {
        "message": state["message"] + " -> Processed by B", 
        "step_count": state["step_count"] + 1
    }

# 3. Build the Graph
builder = StateGraph(GraphState)

# Add our nodes to the graph (give them string names)
builder.add_node("node_a", node_a)
builder.add_node("node_b", node_b)

# 4. Define the Edges (The Control Flow)
builder.add_edge(START, "node_a")  # Start must go to A
builder.add_edge("node_a", "node_b") # A must go to B
builder.add_edge("node_b", END)      # B must end

# 5. Compile (Locks the graph and readies the execution engine)
workflow = builder.compile()

# --- Execution ---
print("Executing Graph...\n")
# We invoke it with an initial state
final_state = workflow.invoke({"message": "Initial Input", "step_count": 0})

print(f"\nFinal Graph State: {final_state}")