import time
from enum import Enum
from typing import Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

# ==========================================
# 1. State & Constants
# ==========================================
MAX_ATTEMPTS = 3
MAX_TOOL_CALLS = 5
OVERALL_BUDGET_SECONDS = 15.0

class TerminalReason(str, Enum):
    SUCCESS = "success"
    MAX_RETRIES = "max_retries_exhausted"
    MAX_TOOLS = "max_tool_calls_exhausted"
    TIMEOUT = "overall_deadline_exceeded"
    UNSAFE = "security_denial"

class AgentState(TypedDict):
    scenario: str
    result: Optional[str]
    error_type: Optional[str]

    # Budgets
    attempts: int
    tool_calls: int
    elapsed_time: float

    # Terminal Status
    is_terminal: bool
    terminal_reason: Optional[TerminalReason]

# ==========================================
# 2. Worker Node
# ==========================================
def work_node(state: AgentState):
    """Simulates agent work that consumes different budgets based on the scenario."""
    attempts = state.get("attempts", 0) + 1
    tool_calls = state.get("tool_calls", 0) + 1
    elapsed = state.get("elapsed_time", 0.0)
    
    print(f"\n  [Work Node] Executing... (Attempt: {attempts}, Tools: {tool_calls}, Time: {elapsed}s)")
    
    # Update budgets
    updates = {"attempts": attempts, "tool_calls": tool_calls}
    
    if state["scenario"] == "Success Scenario":
        updates["elapsed_time"] = elapsed + 2.0
        updates["result"] = "Operation successful."
        updates["error_type"] = None
        
    elif state["scenario"] == "Retry Exhaustion":
        updates["elapsed_time"] = elapsed + 1.0
        updates["error_type"] = "transient_error"
        
    elif state["scenario"] == "Tool Exhaustion":
        # Simulates a loop where the agent isn't erroring, but keeps invoking tools infinitely
        updates["elapsed_time"] = elapsed + 1.0
        updates["tool_calls"] = tool_calls + 2 # Burns tools fast
        updates["error_type"] = "transient_error"
        
    elif state["scenario"] == "Timeout Exhaustion":
        updates["elapsed_time"] = elapsed + 10.0 # Extremely slow operation
        updates["error_type"] = "transient_error"
        
    elif state["scenario"] == "Immediate Denial":
        updates["elapsed_time"] = elapsed + 0.1
        updates["error_type"] = "permission_denied"

    return updates

# ==========================================
# 3. Budget & Evaluation Node
# ==========================================
def evaluate_node(state: AgentState):
    """Checks all budgets and semantic conditions before allowing a retry."""
    print("  [Evaluator] Checking budgets and semantic conditions...")
    
    # 1. Semantic Success
    if state.get("result") and not state.get("error_type"):
        print("    -> Semantic Success. Routing to Terminal.")
        return {"is_terminal": True, "terminal_reason": TerminalReason.SUCCESS}
        
    # 2. Hard Security Denial
    if state.get("error_type") == "permission_denied":
        print("    -> Hard Denial. Unsafe to continue.")
        return {"is_terminal": True, "terminal_reason": TerminalReason.UNSAFE}
        
    # 3. Check Overall Time Budget
    if state["elapsed_time"] >= OVERALL_BUDGET_SECONDS:
        print(f"    -> Overall Time Budget Exhausted ({state['elapsed_time']}s / {OVERALL_BUDGET_SECONDS}s).")
        return {"is_terminal": True, "terminal_reason": TerminalReason.TIMEOUT}
        
    # 4. Check Tool Budget
    if state["tool_calls"] >= MAX_TOOL_CALLS:
        print(f"    -> Tool Budget Exhausted ({state['tool_calls']} / {MAX_TOOL_CALLS}).")
        return {"is_terminal": True, "terminal_reason": TerminalReason.MAX_TOOLS}
        
    # 5. Check Retry Budget
    if state["attempts"] >= MAX_ATTEMPTS:
        print(f"    -> Retry Budget Exhausted ({state['attempts']} / {MAX_ATTEMPTS}).")
        return {"is_terminal": True, "terminal_reason": TerminalReason.MAX_RETRIES}
        
    # If we made it here, we have budget to recover!
    print("    -> Budgets look good. Authorized to attempt recovery.")
    return {"is_terminal": False, "terminal_reason": None}

# ==========================================
# 4. Terminal Node
# ==========================================
def terminal_node(state: AgentState):
    """Centralized cleanup, logging, and user-facing message formatting."""
    reason = state["terminal_reason"]
    print(f"\n  [TERMINAL NODE] Shutting down workflow. Reason: {reason.value.upper()}")
    
    if reason == TerminalReason.SUCCESS:
        print("    [User Output] -> Task completed successfully!")
    elif reason == TerminalReason.UNSAFE:
        print("    [User Output] -> Request denied due to missing permissions.")
    elif reason == TerminalReason.TIMEOUT:
        print("    [User Output] -> Request timed out. The service is currently overloaded.")
    else:
        print("    [User Output] -> Agent could not complete the task within allowed limits.")
        
    return {}

# ==========================================
# 5. Router
# ==========================================
def route_evaluation(state: AgentState) -> Literal["terminal_node", "work_node"]:
    if state["is_terminal"]:
        return "terminal_node"
    return "work_node" # In a real app, this might route to a specific recovery node first

# ==========================================
# 6. Build Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("work_node", work_node)
builder.add_node("evaluate", evaluate_node)
builder.add_node("terminal_node", terminal_node)

builder.add_edge(START, "work_node")
builder.add_edge("work_node", "evaluate")
builder.add_conditional_edges("evaluate", route_evaluation)
builder.add_edge("terminal_node", END)

graph = builder.compile()

# ==========================================
# 7. Execution Scenarios
# ==========================================
def run(scenario: str):
    print(f"\n\n{'='*60}\n=== SCENARIO: {scenario.upper()} ===\n{'='*60}")
    graph.invoke({
        "scenario": scenario, "result": None, "error_type": None,
        "attempts": 0, "tool_calls": 0, "elapsed_time": 0.0,
        "is_terminal": False, "terminal_reason": None
    })

run("Success Scenario")
run("Retry Exhaustion")
run("Tool Exhaustion")
run("Timeout Exhaustion")
run("Immediate Denial")