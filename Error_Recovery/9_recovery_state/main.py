from typing import Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph


# ==========================================
# 1. Strict Recovery State Schema
# ==========================================
class AgentState(TypedDict):
    scenario: str
    result: Optional[str]

    # Explicit Error Tracking
    error_type: Optional[str]
    error_message: Optional[str]
    failed_node: Optional[str]

    # Budget Tracking
    retry_count: int
    fallback_count: int

    # Lifecycle Tracking
    recovery_action: Optional[Literal["retry", "fallback", "abort"]]
    recovery_status: Literal["none", "failed", "recovering", "recovered", "exhausted"]

# ==========================================
# 2. Worker Node (Can Fail or Succeed)
# ==========================================
def work_node(state: AgentState):
    """Simulates primary work. Will fail on the first attempt in most scenarios."""
    attempt = state.get("retry_count", 0)
    print(f"\n  [Work Node] Executing task... (Attempt {attempt + 1})")
    
    # Simulate a transient failure on the first try
    if attempt == 0 and state["scenario"] in ["Timeout Scenario", "Persistent Timeout"]:
        print("    -> HTTP 504 Gateway Timeout.")
        return {
            "result": None,
            "error_type": "timeout",
            "error_message": "Temporary network timeout.",
            "failed_node": "work_node",
            "recovery_status": "failed",
        }
        
    if state["scenario"] == "Permission Denied":
        print("    -> HTTP 403 Forbidden.")
        return {
            "result": None,
            "error_type": "permission",
            "error_message": "Invalid API Key.",
            "failed_node": "work_node",
            "recovery_status": "failed",
        }
        
    if attempt == 1 and state["scenario"] == "Persistent Timeout":
        print("    -> HTTP 504 Gateway Timeout.")
        return {
            "result": None,
            "error_type": "timeout",
            "error_message": "Temporary network timeout.",
            "failed_node": "work_node",
            "recovery_status": "failed",
        }

    print("    -> Success!")
    # CRITICAL: Normalize/heal the state so downstream nodes don't think we are still failing
    return {
        "result": "Primary task data retrieved.",
        "error_type": None,
        "error_message": None,
        "failed_node": None,
        "recovery_action": None,
        "recovery_status": "recovered" if attempt > 0 else "none",
    }

# ==========================================
# 3. Policy & Routing Nodes
# ==========================================
def recovery_policy_node(state: AgentState):
    """Evaluates the explicit state and decides on a recovery action."""
    print(f"  [Policy Layer] Analyzing state. Status: '{state['recovery_status']}', Error: '{state['error_type']}'")
    
    if state["error_type"] == "timeout":
        if state["retry_count"] < 2:
            print("    -> Action: RETRY")
            return {"recovery_action": "retry", "recovery_status": "recovering"}
        else:
            print("    -> Max retries hit. Action: FALLBACK")
            return {"recovery_action": "fallback", "recovery_status": "recovering"}

    print("    -> Fatal error. Action: ABORT")
    return {"recovery_action": "abort", "recovery_status": "exhausted"}

def route_recovery(state: AgentState) -> Literal["retry_node", "fallback_node", "__end__"]:
    action = state["recovery_action"]
    if action == "retry": return "retry_node"
    if action == "fallback": return "fallback_node"
    return "__end__"

# ==========================================
# 4. Action Nodes
# ==========================================
def retry_node(state: AgentState):
    """Increments the budget counter before looping back to work."""
    print("  [Recovery Executor] Incrementing retry budget...")
    return {"retry_count": state["retry_count"] + 1}

def fallback_node(state: AgentState):
    """Executes backup logic and heals the state."""
    print("  [Fallback Executor] Running degraded fallback method...")
    return {
        "fallback_count": state["fallback_count"] + 1,
        "result": "Fallback data retrieved.",
        "error_type": None,
        "error_message": None,
        "failed_node": None,
        "recovery_action": None,
        "recovery_status": "recovered",
    }

# ==========================================
# 5. Build Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("work_node", work_node)
builder.add_node("recovery_policy", recovery_policy_node)
builder.add_node("retry_node", retry_node)
builder.add_node("fallback_node", fallback_node)

builder.add_edge(START, "work_node")

# If work failed, go to policy. If success, end.
def route_after_work(state: AgentState):
    if state["recovery_status"] == "failed": return "recovery_policy"
    return "__end__"

builder.add_conditional_edges("work_node", route_after_work)

# Route based on the policy decision
builder.add_conditional_edges("recovery_policy", route_recovery)

# Loop retry back to work
builder.add_edge("retry_node", "work_node")
builder.add_edge("fallback_node", END)

graph = builder.compile()

# ==========================================
# 6. Execution Scenarios
# ==========================================
def run(scenario: str):
    print(f"\n\n{'='*60}\n=== SCENARIO: {scenario.upper()} ===\n{'='*60}")
    
    initial_state = {
        "scenario": scenario, "result": None, "error_type": None, "error_message": None,
        "failed_node": None, "retry_count": 0, "fallback_count": 0, 
        "recovery_action": None, "recovery_status": "none"
    }
    
    final_state = graph.invoke(initial_state)
    print(f"  FINAL STATE -> Result: {final_state.get('result')} | Status: {final_state['recovery_status']}")

run("Happy Path")
run("Timeout Scenario")
run("Persistent Timeout")
run("Permission Denied")