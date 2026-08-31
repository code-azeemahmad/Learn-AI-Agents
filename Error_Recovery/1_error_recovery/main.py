import random
from typing import Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

# ==========================================
# 1. State & Constants
# ==========================================
MAX_RETRIES = 2

class AgentState(TypedDict):
    scenario: str
    tool_name: str
    result: Optional[str]
    error: Optional[str]
    error_type: Optional[str]
    next_action: Optional[str]
    attempts: int

# ==========================================
# 2. Simulated Flaky Tool
# ==========================================
def execute_primary_tool(state: AgentState):
    """Simulates a tool that fails in predictable ways based on the scenario."""
    attempts = state.get("attempts", 0) + 1
    print(f"\n  [Primary Tool] Executing '{state['tool_name']}' (Attempt {attempts})...")
    
    if state["scenario"] == "Transient Timeout":
        if attempts <= 2:
            return {"error": "Connection timed out after 5000ms", "attempts": attempts}
        return {"result": "Success on attempt 3!", "error": None, "attempts": attempts}
        
    elif state["scenario"] == "Service Down":
        return {"error": "503 Service Unavailable", "attempts": attempts}
        
    elif state["scenario"] == "Auth Failure":
        return {"error": "403 Forbidden. Invalid token.", "attempts": attempts}
        
    elif state["scenario"] == "Infinite Loop":
        return {"error": "Connection timed out after 5000ms", "attempts": attempts}
        
    return {"result": "Immediate Success!", "error": None, "attempts": attempts}

# ==========================================
# 3. Graph Nodes
# ==========================================
def classifier_node(state: AgentState):
    """Categorizes the raw error string into a known system error_type."""
    if not state.get("error"):
        print("  [Classifier] No error detected. Setting action to END.")
        return {"error_type": None, "next_action": "end"}
        
    error_msg = state["error"].lower()
    print(f"  [Classifier] Detected Error: '{state['error']}'")
    
    # 1. Classify the exact failure
    if "timeout" in error_msg:
        error_type = "timeout"
        next_action = "retry"
    elif "503" in error_msg or "unavailable" in error_msg:
        error_type = "service_unavailable"
        next_action = "fallback"
    elif "403" in error_msg or "forbidden" in error_msg:
        error_type = "permission_denied"
        next_action = "abort"
    else:
        error_type = "unknown"
        next_action = "abort"
        
    print(f"    -> Classified as '{error_type}'. Suggested Action: '{next_action}'.")
    return {"error_type": error_type, "next_action": next_action}

def fallback_tool_node(state: AgentState):
    """A backup tool that runs when the primary service is down."""
    print(f"  [Fallback Tool] Primary failed. Executing fallback logic for '{state['tool_name']}'...")
    return {"result": "Success via Fallback Method", "error": None}

def abort_node(state: AgentState):
    """Handles permanent or security-related failures."""
    print("  [Abort Handler] Executing Graceful Failure. Rolling back state or logging incident.")
    return {"result": f"Task Failed. Reason: {state['error']}"}

# ==========================================
# 4. Deterministic Router
# ==========================================
def recovery_router(state: AgentState) -> Literal["retry_tool", "fallback_tool", "abort", "__end__"]:
    """Reads the Classifier's suggested action and enforces budget constraints."""
    
    # 1. Success Path
    if state["next_action"] == "end":
        return "__end__"
        
    # 2. Hard Limits (Overrides the Classifier's suggestion)
    if state["next_action"] == "retry" and state["attempts"] >= MAX_RETRIES:
        print(f"  [Router] Retry limit ({MAX_RETRIES}) reached. Overriding 'retry' and forcing 'abort'.")
        return "abort"
        
    # 3. Dynamic Routing
    if state["next_action"] == "retry":
        print("  [Router] Routing back to Primary Tool...")
        return "retry_tool"
        
    if state["next_action"] == "fallback":
        print("  [Router] Routing to Fallback Tool...")
        return "fallback_tool"
        
    print("  [Router] Routing to Abort Handler...")
    return "abort"

# ==========================================
# 5. Build Graph
# ==========================================
builder = StateGraph(AgentState)

# Nodes
builder.add_node("primary_tool", execute_primary_tool)
builder.add_node("classifier", classifier_node)
builder.add_node("fallback_tool", fallback_tool_node)
builder.add_node("abort", abort_node)

# Primary Loop
builder.add_edge(START, "primary_tool")
builder.add_edge("primary_tool", "classifier")

# Routing Logic
builder.add_conditional_edges("classifier", recovery_router, {
    "__end__": END,
    "retry_tool": "primary_tool",
    "fallback_tool": "fallback_tool",
    "abort": "abort"
})

builder.add_edge("fallback_tool", END)
builder.add_edge("abort", END)

graph = builder.compile()

# ==========================================
# 6. Execution Scenarios
# ==========================================
def run(scenario: str):
    print(f"\n\n{'='*60}\n=== SCENARIO: {scenario.upper()} ===\n{'='*60}")
    initial_state = {"scenario": scenario, "tool_name": "Fetch User Data", "attempts": 0}
    final = graph.invoke(initial_state)
    print(f"  FINAL RESULT: {final.get('result')}")

run("Happy Path")
run("Service Down")
run("Auth Failure")
run("Transient Timeout") # Note: MAX_RETRIES is 2. So if it needs 3, it will fail. Let's see what happens.
run("Infinite Loop")