from enum import Enum
from typing import Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

# ==========================================
# 1. State & Constants
# ==========================================
MAX_RETRIES = 2
OVERALL_BUDGET = 20.0  # The absolute maximum seconds the whole graph can take

class ErrorType(str, Enum):
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"

class AgentState(TypedDict):
    scenario: str
    action_type: Literal["read", "write"]
    attempts: int
    elapsed_time: float
    result: Optional[str]
    error_type: Optional[ErrorType]
    next_action: Optional[Literal["retry", "fallback", "abort", "check_status", "finish"]]

# ==========================================
# 2. Simulated Async Tool Node
# ==========================================
def call_primary_node(state: AgentState):
    """
    Simulates:
    @task(timeout=5.0)
    async def call_primary(): ...
    """
    attempts = state.get("attempts", 0) + 1
    elapsed = state.get("elapsed_time", 0.0)
    print(f"\n  [Tool] Executing primary operation... (Attempt {attempts} | Total Elapsed: {elapsed}s)")
    
    # Simulate how long this specific attempt took
    if state["scenario"] == "Budget Exhausted":
        attempt_duration = 10.0 # Extremely slow
    elif state["scenario"] == "Persistent Timeout":
        attempt_duration = 5.0 # Fails right at the timeout limit
    else:
        attempt_duration = 5.0 if attempts == 1 else 1.0 # First try times out, second is fast
        
    elapsed += attempt_duration
    
    # 1. Did the entire graph run out of time?
    if elapsed > OVERALL_BUDGET:
        print(f"    -> FATAL: Overall graph deadline ({OVERALL_BUDGET}s) exceeded. Current: {elapsed}s.")
        return {"elapsed_time": elapsed, "error_type": ErrorType.TIMEOUT, "attempts": attempts}
        
    # 2. Did this specific node attempt timeout?
    if attempt_duration >= 5.0:
        print("    -> NodeTimeoutError: Operation exceeded per-attempt timeout (5.0s).")
        return {"elapsed_time": elapsed, "error_type": ErrorType.TIMEOUT, "attempts": attempts}
        
    print("    -> Success!")
    return {"elapsed_time": elapsed, "result": "Operation complete.", "error_type": None, "attempts": attempts}

# ==========================================
# 3. Recovery Nodes
# ==========================================
def recovery_node(state: AgentState):
    """The brain that decides what to do when a NodeTimeoutError is raised."""
    print("  [Recovery Layer] Analyzing Timeout...")
    
    # 1. Enforce Overall Graph Deadline
    if state["elapsed_time"] >= OVERALL_BUDGET:
        print(f"    -> Overall deadline exceeded. Cannot safely retry. Action: ABORT.")
        return {"next_action": "abort"}
        
    # 2. Enforce Per-Node Retry Budget
    if state["attempts"] >= MAX_RETRIES + 1:
        print(f"    -> Max retries ({MAX_RETRIES}) reached. Action: FALLBACK.")
        return {"next_action": "fallback"}
        
    # 3. Guard Side-Effects on Write Operations
    if state["action_type"] == "write":
        print(f"    -> Write operation timed out. Outcome UNKNOWN. Action: CHECK STATUS.")
        return {"next_action": "check_status"}
        
    # 4. Safe to Retry
    print("    -> Transient read error within budget. Action: RETRY.")
    return {"next_action": "retry"}

def fallback_node(state: AgentState):
    print("  [Fallback Tool] Executing faster, degraded fallback operation...")
    return {"result": "Fallback success.", "error_type": None, "elapsed_time": state["elapsed_time"] + 1.0}

def check_status_node(state: AgentState):
    print("  [Idempotency Check] Querying database to see if write operation actually succeeded...")
    print("    -> Data found. The write succeeded despite the timeout.")
    return {"result": "Write confirmed via status check.", "error_type": None}

def handle_result_node(state: AgentState):
    print(f"  [Output] Final Result: {state.get('result', 'Task Failed.')} (Total Time: {state['elapsed_time']}s)")
    return {}

# ==========================================
# 4. Routing Logic
# ==========================================
def route_after_tool(state: AgentState) -> Literal["handle_result", "recovery"]:
    if state.get("error_type") is None:
        return "handle_result"
    return "recovery"

def route_after_recovery(state: AgentState) -> Literal["retry_tool", "fallback_tool", "check_status", "abort_workflow"]:
    action = state["next_action"]
    if action == "retry": return "retry_tool"
    if action == "fallback": return "fallback_tool"
    if action == "check_status": return "check_status"
    return "abort_workflow"

# ==========================================
# 5. Build Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("call_primary", call_primary_node)
builder.add_node("handle_result", handle_result_node)
builder.add_node("recovery", recovery_node)
builder.add_node("fallback", fallback_node)
builder.add_node("check_status", check_status_node)

builder.add_edge(START, "call_primary")
builder.add_conditional_edges("call_primary", route_after_tool)

builder.add_conditional_edges("recovery", route_after_recovery, {
    "retry_tool": "call_primary",
    "fallback_tool": "fallback",
    "check_status": "check_status",
    "abort_workflow": "handle_result"
})

builder.add_edge("fallback", "handle_result")
builder.add_edge("check_status", "handle_result")
builder.add_edge("handle_result", END)

graph = builder.compile()

# ==========================================
# 6. Execution Scenarios
# ==========================================
def run(scenario: str, action_type: str = "read"):
    print(f"\n\n{'='*50}\n=== SCENARIO: {scenario.upper()} ===\n{'='*50}")
    graph.invoke({"scenario": scenario, "action_type": action_type, "attempts": 0, "elapsed_time": 0.0, "result": None, "error_type": None})

# Case 1: Times out once, succeeds on retry
run("Simple Timeout")

# Case 2: Times out multiple times, uses up retries, falls back
run("Persistent Timeout")

# Case 3: The graph is allotted 20 seconds. It takes 10s per try. It dies before Attempt 3.
run("Budget Exhausted")

# Case 4: A write operation times out. The graph routes to check if it actually executed.
run("Write Timeout", action_type="write")