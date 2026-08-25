from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict


# 1. State Schema (No reducer, meaning default overwrite behavior)
class State(TypedDict):
    count: int

# 2. Node
def increment(state: State):
    current_count = state.get("count", 0)
    print(f"  [Node] Incrementing from {current_count} to {current_count + 1}")
    return {"count": current_count + 1}

# 3. Build Graph
builder = StateGraph(State)
builder.add_node("increment", increment)
builder.add_edge(START, "increment")
builder.add_edge("increment", END)

# 4. Configure Persistence (The Checkpointer)
checkpointer = InMemorySaver()

# Compile the graph WITH the checkpointer
graph = builder.compile(checkpointer=checkpointer)

# ==========================================
# 5. Execution & Verification
# ==========================================

print("--- Thread A: First Invocation ---")
config_a = {"configurable": {"thread_id": "thread-a"}}
# We pass initial state here
result_a1 = graph.invoke({"count": 0}, config_a)
print(f"Result A1: {result_a1}")

print("\n--- Thread A: Second Invocation ---")
# Because of the checkpointer, we DO NOT need to pass {"count": 1}. 
# We pass None. The runtime loads the checkpoint and continues.
result_a2 = graph.invoke(None, config_a)
print(f"Result A2: {result_a2}")

print("\n--- Thread B: First Invocation (Isolation Test) ---")
config_b = {"configurable": {"thread_id": "thread-b"}}
# We invoke a completely different thread. It should start fresh.
result_b1 = graph.invoke({"count": 0}, config_b)
print(f"Result B1: {result_b1}")

print("\n--- Inspecting Thread A's Checkpoint directly ---")
# Fetching the state without running the graph
snapshot_a = graph.get_state(config_a)
print(f"Thread A values: {snapshot_a.values}")