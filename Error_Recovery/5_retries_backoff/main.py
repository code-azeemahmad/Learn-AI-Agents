import random
from typing import Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

# ==========================================
# 1. State & Constants
# ==========================================
MAX_RETRIES = 3
BASE_DELAY = 1.0
MAX_DELAY = 10.0

class AgentState(TypedDict):
    scenario: str
    action_type: Literal["read", "write"]
    attempts: int
    delay_seconds: float
    success: bool
    error: Optional[str]
    order_exists: bool # For idempotency checks

# ==========================================
# 2. Nodes
# ==========================================
def call_service_node(state: AgentState):
    """Simulates a failing external API call."""
    attempts = state.get("attempts", 0) + 1
    
    # Simulate the backoff wait (in real life, use async sleep, here we just print)
    if attempts > 1:
        print(f"  [Wait] Sleeping for {state['delay_seconds']:.2f} seconds before retry...")
        
    print(f"\n  [Service] Executing {state['action_type'].upper()} operation... (Attempt {attempts})")
    
    # 1. Permanent Failure Scenario
    if state["scenario"] == "Permission Denied":
        print("    -> HTTP 403 Forbidden.")
        return {"attempts": attempts, "success": False, "error": "permission_denied"}
        
    # 2. Transient Timeout Scenario
    if state["scenario"] == "Timeout (Read)" or state["scenario"] == "Timeout (Write)":
        if attempts < 3:
            print("    -> HTTP 504 Gateway Timeout.")
            return {"attempts": attempts, "success": False, "error": "timeout"}
            
    print("    -> Success!")
    return {"attempts": attempts, "success": True, "error": None}

def check_status_node(state: AgentState):
    """
    IDEMPOTENCY CHECK: Verifies if the side-effect actually occurred 
    before we blindly retry a write operation.
    """
    print("  [Idempotency Check] Checking remote server to see if order was actually created despite the timeout...")
    
    # We simulate that the server DID create the order, the connection just dropped.
    print("    -> DANGER AVERTED: Order already exists on the server! A blind retry would have double-charged.")
    return {"order_exists": True}

def calculate_backoff_node(state: AgentState):
    """Calculates Exponential Backoff with Jitter."""
    attempts = state["attempts"]
    
    # Exponential calculation: base * (2 ^ (attempts - 1))
    raw_delay = BASE_DELAY * (2 ** (attempts - 1))
    
    # Add Jitter (0 to 500ms)
    jitter = random.uniform(0, 0.5)
    
    # Cap at MAX_DELAY
    final_delay = min(raw_delay + jitter, MAX_DELAY)
    
    print(f"  [Backoff Calculator] Computed delay for next attempt: {final_delay:.2f}s (Jitter applied)")
    return {"delay_seconds": final_delay}

# ==========================================
# 3. Router
# ==========================================
def retry_router(state: AgentState) -> Literal["backoff", "check_status", "__end__"]:
    
    # 1. Success Path
    if state["success"]:
        return "__end__"
        
    # 2. Non-Retryable Error Path
    if state["error"] == "permission_denied":
        print("  [Router] Fatal error (403). Aborting workflow.")
        return "__end__"
        
    # 3. Guard against duplicate side-effects (Write Operations)
    if state["action_type"] == "write" and state["error"] == "timeout":
        print("  [Router] Write operation timed out. Routing to status check to prevent double-execution.")
        return "check_status"
        
    # 4. Enforce Retry Budget
    if state["attempts"] >= MAX_RETRIES:
        print("  [Router] Max retries exhausted. Failing gracefully.")
        return "__end__"
        
    # 5. Safe to Retry (Read operations)
    print("  [Router] Transient read error. Routing to backoff calculator.")
    return "backoff"

def post_status_router(state: AgentState) -> Literal["backoff", "__end__"]:
    if state.get("order_exists"):
        print("  [Router] Order confirmed. Exiting successfully without retrying.")
        return "__end__"
        
    # If the order didn't exist, it is now safe to retry the write
    print("  [Router] Order does not exist. Safe to retry write operation.")
    return "backoff"

# ==========================================
# 4. Build Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("call_service", call_service_node)
builder.add_node("check_status", check_status_node)
builder.add_node("backoff", calculate_backoff_node)

builder.add_edge(START, "call_service")

# After calling the service, decide what to do
builder.add_conditional_edges("call_service", retry_router)

# If it's a write, we check status. Then we route based on the check.
builder.add_conditional_edges("check_status", post_status_router)

# Once backoff is calculated, loop back to the service
builder.add_edge("backoff", "call_service")

graph = builder.compile()

# ==========================================
# 5. Execution Scenarios
# ==========================================
def run(scenario: str, action_type: str):
    print(f"\n\n{'='*60}\n=== SCENARIO: {scenario.upper()} ===\n{'='*60}")
    graph.invoke({
        "scenario": scenario, "action_type": action_type,
        "attempts": 0, "delay_seconds": 0.0, "success": False, "error": None, "order_exists": False
    })

# Scenario 1: A basic read operation that fails temporarily. Safe to blind retry.
run("Timeout (Read)", "read")

# Scenario 2: A fatal error that should never be retried.
run("Permission Denied", "read")

# Scenario 3: A write operation that times out. MUST check idempotency!
run("Timeout (Write)", "write")