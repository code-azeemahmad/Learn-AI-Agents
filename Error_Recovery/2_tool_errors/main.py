from enum import Enum
from typing import Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

# ==========================================
# 1. State & Constants
# ==========================================
MAX_RETRIES = 2

class ErrorType(str, Enum):
    TIMEOUT = "timeout"
    PERMISSION = "permission"
    SERVICE_UNAVAILABLE = "service_unavailable"
    UNKNOWN = "unknown"

class AgentState(TypedDict):
    scenario: str
    attempts: int
    result: Optional[str]
    error_type: Optional[ErrorType]
    error_message: Optional[str]
    next_action: Optional[Literal["retry", "fallback", "abort", "finish"]]

# ==========================================
# 2. Simulated Primary Tool
# ==========================================
def primary_tool_node(state: AgentState):
    """Simulates a tool that fails in specific ways based on the scenario."""
    attempt = state.get("attempts", 0) + 1
    print(f"\n  [Primary Tool] Executing database query... (Attempt {attempt})")
    
    if state["scenario"] == "Timeout Scenario":
        if attempt <= 1:
            print("    -> Network timeout occurred.")
            return {
                "attempts": attempt,
                "result": None,
                "error_type": ErrorType.TIMEOUT,
                "error_message": "Connection timed out after 5 seconds.",
            }
        print("    -> Success on retry!")
        return {
            "attempts": attempt,
            "result": "Fetched 15 customer records.",
            "error_type": None,
            "error_message": None,
        }
        
    elif state["scenario"] == "Permission Denied Scenario":
        print("    -> HTTP 403 Forbidden.")
        return {
            "attempts": attempt,
            "result": None,
            "error_type": ErrorType.PERMISSION,
            "error_message": "User lacks privileges to view customer records.",
        }
        
    elif state["scenario"] == "Service Down Scenario":
        print("    -> HTTP 503 Service Unavailable.")
        return {
            "attempts": attempt,
            "result": None,
            "error_type": ErrorType.SERVICE_UNAVAILABLE,
            "error_message": "Primary database replica is offline.",
        }
        
    elif state["scenario"] == "Persistent Timeout":
        print("    -> Network timeout occurred.")
        return {
            "attempts": attempt,
            "result": None,
            "error_type": ErrorType.TIMEOUT,
            "error_message": "Connection timed out after 5 seconds.",
        }

    return {"attempts": attempt, "result": "Success!", "error_type": None}

# ==========================================
# 3. Graph Nodes
# ==========================================
def recovery_node(state: AgentState):
    """
    Deterministically decides the recovery strategy based on the explicit error type.
    """
    error_type = state["error_type"]
    print(f"  [Recovery Layer] Analyzing error type: {error_type}")
    
    if error_type == ErrorType.TIMEOUT:
        if state["attempts"] >= MAX_RETRIES:
            print(f"    -> Max retries ({MAX_RETRIES}) reached. Escalating to fallback.")
            return {"next_action": "fallback"}
        print("    -> Transient failure detected. Action: RETRY.")
        return {"next_action": "retry"}
        
    elif error_type == ErrorType.PERMISSION:
        print("    -> Security boundary failure detected. Action: ABORT.")
        return {"next_action": "abort"}
        
    elif error_type == ErrorType.SERVICE_UNAVAILABLE:
        print("    -> Primary service down. Action: FALLBACK.")
        return {"next_action": "fallback"}
        
    return {"next_action": "abort"}

def fallback_tool_node(state: AgentState):
    """Executes a secondary system when the primary fails."""
    print("  [Fallback Tool] Executing read-only cache query...")
    return {
        "result": "Fetched 15 customer records (from read-only cache).",
        "error_type": None,
        "error_message": None
    }

def handle_result_node(state: AgentState):
    """Wraps up a successful execution."""
    print(f"  [Output] Final Result: {state['result']}")
    return {"next_action": "finish"}

# ==========================================
# 4. Routing Logic
# ==========================================
def route_after_tool(state: AgentState) -> Literal["handle_result", "recovery"]:
    if state.get("error_type") is None:
        return "handle_result"
    return "recovery"

def route_after_recovery(state: AgentState) -> Literal["primary_tool", "fallback_tool", "__end__"]:
    action = state["next_action"]
    if action == "retry":
        return "primary_tool"
    if action == "fallback":
        return "fallback_tool"
    return "__end__"

# ==========================================
# 5. Build Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("primary_tool", primary_tool_node)
builder.add_node("handle_result", handle_result_node)
builder.add_node("recovery", recovery_node)
builder.add_node("fallback_tool", fallback_tool_node)

builder.add_edge(START, "primary_tool")

# Check if the tool threw an error
builder.add_conditional_edges("primary_tool", route_after_tool)

# Read the recovery node's deterministic decision
builder.add_conditional_edges("recovery", route_after_recovery)

builder.add_edge("fallback_tool", "handle_result")
builder.add_edge("handle_result", END)

graph = builder.compile()

# ==========================================
# 6. Execution Scenarios
# ==========================================
def run_scenario(scenario: str):
    print(f"\n\n{'='*50}\n=== SCENARIO: {scenario.upper()} ===\n{'='*50}")
    graph.invoke({"scenario": scenario, "attempts": 0, "result": None, "error_type": None, "error_message": None, "next_action": None})

run_scenario("Timeout Scenario")
run_scenario("Permission Denied Scenario")
run_scenario("Service Down Scenario")
run_scenario("Persistent Timeout")