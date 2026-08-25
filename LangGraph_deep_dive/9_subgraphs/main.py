from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

# =================================================================
# PATTERN 1: Different Schemas + Wrapper Node
# =================================================================
print("=== PATTERN 1: Different Schemas ===")

# --- Child Graph (Different Schema) ---
class ChildState(TypedDict):
    text: str

def uppercase(state: ChildState):
    return {"text": state["text"].upper()}

def add_prefix(state: ChildState):
    return {"text": "Result: " + state["text"]}

child_builder = StateGraph(ChildState)
child_builder.add_node("uppercase", uppercase)
child_builder.add_node("add_prefix", add_prefix)
child_builder.add_edge(START, "uppercase")
child_builder.add_edge("uppercase", "add_prefix")
child_builder.add_edge("add_prefix", END)

child_graph = child_builder.compile()

# --- Parent Graph (Different Schema) ---
class ParentState(TypedDict):
    input_text: str
    output_text: str

def call_subgraph(state: ParentState):
    print(f"  [Parent Wrapper] Transforming '{state['input_text']}' for subgraph...")
    # 1. Transform parent state to child state
    child_input = {"text": state["input_text"]}
    
    # 2. Invoke subgraph
    child_result = child_graph.invoke(child_input)
    
    print(f"  [Parent Wrapper] Received '{child_result['text']}' from subgraph...")
    
    # 3. Transform child result back to parent state
    return {"output_text": child_result["text"]}

parent_builder_1 = StateGraph(ParentState)
parent_builder_1.add_node("call_subgraph", call_subgraph)
parent_builder_1.add_edge(START, "call_subgraph")
parent_builder_1.add_edge("call_subgraph", END)

parent_graph_1 = parent_builder_1.compile()

# Execute Pattern 1
result_1 = parent_graph_1.invoke({"input_text": "langgraph", "output_text": ""})
print(f"Pattern 1 Final State: {result_1}\n")


# =================================================================
# PATTERN 2: Shared Schema + Direct Injection
# =================================================================
print("=== PATTERN 2: Shared Schema ===")

# --- Shared State ---
class SharedState(TypedDict):
    text: str

# --- Child Graph (Shared Schema) ---
def uppercase_shared(state: SharedState):
    print("  [Subgraph] Uppercasing...")
    return {"text": state["text"].upper()}

def add_prefix_shared(state: SharedState):
    print("  [Subgraph] Adding prefix...")
    return {"text": "Result: " + state["text"]}

shared_child_builder = StateGraph(SharedState)
shared_child_builder.add_node("uppercase_shared", uppercase_shared)
shared_child_builder.add_node("add_prefix_shared", add_prefix_shared)
shared_child_builder.add_edge(START, "uppercase_shared")
shared_child_builder.add_edge("uppercase_shared", "add_prefix_shared")
shared_child_builder.add_edge("add_prefix_shared", END)

shared_child_graph = shared_child_builder.compile()

# --- Parent Graph (Shared Schema) ---
parent_builder_2 = StateGraph(SharedState)

# MAGIC HAPPENS HERE: We pass the compiled subgraph directly into add_node!
# No wrapper function is needed because the states match.
parent_builder_2.add_node("my_subgraph", shared_child_graph)

parent_builder_2.add_edge(START, "my_subgraph")
parent_builder_2.add_edge("my_subgraph", END)

parent_graph_2 = parent_builder_2.compile()

# Execute Pattern 2
result_2 = parent_graph_2.invoke({"text": "langgraph"})
print(f"Pattern 2 Final State: {result_2}")