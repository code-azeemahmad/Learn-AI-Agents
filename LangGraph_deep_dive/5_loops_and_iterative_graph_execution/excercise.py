from typing import Literal

from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict


# 1. State Schema
class State(TypedDict):
    attempts: int
    success: bool

# ==========================================
# 2. Nodes & Routers
# ==========================================

def attempt_node_eventual_success(state: State):
    """Simulates a tool that fails twice, then succeeds on the 3rd try."""
    attempts = state["attempts"] + 1
    success = attempts >= 3  
    print(f"  [Node] Attempt {attempts} executed. Success: {success}")
    return {"attempts": attempts, "success": success}

def attempt_node_always_fails(state: State):
    """Simulates a tool that is completely broken."""
    attempts = state["attempts"] + 1
    success = False  
    print(f"  [Node] Attempt {attempts} executed. Success: {success}")
    return {"attempts": attempts, "success": success}

def safe_router(state: State) -> Literal["attempt", END]: # type: ignore
    """Business logic routing with a safety limit."""
    if state["success"]:
        print("  [Router] Success detected -> Routing to END")
        return END
    if state["attempts"] >= 3:
        print("  [Router] Max attempts (3) reached -> Routing to END (Safety Termination)")
        return END
    
    print("  [Router] Failed but under limit -> Routing to retry")
    return "attempt"

def unsafe_router(state: State) -> Literal["attempt", END]: # type: ignore
    """Buggy routing logic: only stops on success, forgets to check attempt limits."""
    if state["success"]:
        return END
    return "attempt"

# ==========================================
# 3. Helper to Build Graphs
# ==========================================
def build_graph(node_func, router_func):
    builder = StateGraph(State)
    builder.add_node("attempt", node_func)
    builder.add_edge(START, "attempt")
    builder.add_conditional_edges("attempt", router_func)
    return builder.compile()

# ==========================================
# 4. Execution & Verification
# ==========================================

print("--- CASE 1: Eventual Success ---")
graph_1 = build_graph(attempt_node_eventual_success, safe_router)
result_1 = graph_1.invoke({"attempts": 0, "success": False})
print(f"Final State: {result_1}\n")


print("--- CASE 2: Business Logic Safety Termination ---")
graph_2 = build_graph(attempt_node_always_fails, safe_router)
result_2 = graph_2.invoke({"attempts": 0, "success": False})
print(f"Final State: {result_2}\n")


print("--- CASE 3: Framework Runtime Limit (GraphRecursionError) ---")
graph_3 = build_graph(attempt_node_always_fails, unsafe_router)
try:
    # We pass a config dictionary enforcing a strict recursion limit of 2 super-steps
    graph_3.invoke(
        {"attempts": 0, "success": False},
        {"recursion_limit": 2} 
    )
except GraphRecursionError as e:
    print(f"  [Framework] GraphRecursionError caught! The framework killed the infinite loop.")  # noqa: F541
    print(f"  [Framework Error Details]: {e}")