from typing import Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph


# ==========================================
# 1. State & Constants
# ==========================================
class AgentState(TypedDict):
    scenario: str
    
    # Simulating parallel branch outputs
    architecture: list[str]
    policies: list[str]
    metrics: list[str]
    
    # Tracking Status
    completed: list[str]
    failed: list[str]
    
    # Counters to prevent infinite loops
    retry_count: int
    
    # Required for conditional routing tracking
    next_action: Optional[Literal["synthesize", "recover"]]  # noqa: UP045

# Define branch criticality
CRITICAL_BRANCHES = ["architecture", "policies"]
OPTIONAL_BRANCHES = ["metrics"]

# ==========================================
# 2. Simulated Parallel Branches
# ==========================================
def parallel_execution_node(state: AgentState):
    """Simulates executing 3 tasks in parallel and aggregating their results."""
    print(f"\n{'='*50}\n[Scenario]: {state['scenario']}\n[Execution] Running parallel branches...")
    
    # Always copy lists from state to avoid accidental in-place mutation
    completed = state.get("completed", []).copy()
    failed = []
    
    # We will store all our state updates here to return to LangGraph
    updates = {}
    
    # Branch 1: Architecture
    if "architecture" not in completed:
        print("  -> Fetching Architecture...")
        updates["architecture"] = ["Data: Microservices on AWS"]
        completed.append("architecture")
        
    # Branch 2: Policies
    if "policies" not in completed:
        print("  -> Fetching Policies...")
        if state["scenario"] == "Critical Failure" and state.get("retry_count", 0) == 0:
            print("     HTTP 500: Policy Server Down!")
            failed.append("policies")
        else:
            updates["policies"] = ["Data: SOC2 Compliant"]
            completed.append("policies")
            
    # Branch 3: Metrics (Optional)
    if "metrics" not in completed:
        print("  -> Fetching Metrics...")
        if state["scenario"] in ["Optional Failure", "Critical Failure"] and state.get("retry_count", 0) == 0:
            print("     HTTP 504: Metrics Server Timeout!")
            failed.append("metrics")
        else:
            updates["metrics"] = ["Data: 99.9% Uptime"]
            completed.append("metrics")
            
    updates["completed"] = completed
    updates["failed"] = failed
    
    # LangGraph requires us to explicitly return the keys we want updated
    return updates

# ==========================================
# 3. Evaluation & Recovery Nodes
# ==========================================
def evaluate_node(state: AgentState):
    """Analyzes the partial failures and determines if recovery is needed."""
    failed = state["failed"]
    print(f"\n  [Evaluator] Branches Completed: {state['completed']}")
    print(f"  [Evaluator] Branches Failed: {failed}")
    
    if not failed:
        return {"next_action": "synthesize"}
        
    # Check if any of the failed branches are critical
    critical_failures = [b for b in failed if b in CRITICAL_BRANCHES]
    
    if critical_failures:
        print(f"    -> Critical branches failed: {critical_failures}. Must recover.")
        return {"next_action": "recover"}
        
    # If only optional branches failed, we can just move on (Graceful Degradation)
    print("    -> Only optional branches failed. Proceeding to synthesis in Degraded Mode.")
    return {"next_action": "synthesize"}

def recover_node(state: AgentState):
    """Specifically targets and retries ONLY the failed branches."""
    count = state.get("retry_count", 0) + 1
    print(f"  [Recovery] Isolating failed branches: {state['failed']} (Attempt {count})...")
    # Loop back to the parallel node, which is smart enough to skip completed branches
    return {"retry_count": count}

def synthesize_node(state: AgentState):
    """Generates the final answer, safely extracting list items."""
    print("\n  [Synthesizer] Compiling final report...")
    
    # Safe extraction
    arch = state.get('architecture')
    pol = state.get('policies')
    met = state.get('metrics')
    
    report = "Final Analysis:\n"
    report += f"  - Arch: {arch[0] if arch else 'UNAVAILABLE'}\n"
    report += f"  - Policy: {pol[0] if pol else 'UNAVAILABLE'}\n"
    report += f"  - Metrics: {met[0] if met else 'UNAVAILABLE'}\n"
    
    if state.get("failed"):
        print("    -> Warning added to report regarding missing optional data.")
        
    print(report)
    return {}

# ==========================================
# 4. Router
# ==========================================
def partial_failure_router(state: AgentState) -> Literal["synthesize", "recover"]:
    return state["next_action"]

# ==========================================
# 5. Build Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("execute_parallel", parallel_execution_node)
builder.add_node("evaluate", evaluate_node)
builder.add_node("recover", recover_node)
builder.add_node("synthesize", synthesize_node)

builder.add_edge(START, "execute_parallel")
builder.add_edge("execute_parallel", "evaluate")
builder.add_conditional_edges("evaluate", partial_failure_router)
builder.add_edge("recover", "execute_parallel") # Loops back to try again
builder.add_edge("synthesize", END)

graph = builder.compile()

# ==========================================
# 6. Execution Scenarios
# ==========================================
def run(scenario: str):
    graph.invoke({
        "scenario": scenario, 
        "architecture": [], 
        "policies": [], 
        "metrics": [], 
        "completed": [], 
        "failed": [], 
        "retry_count": 0, 
        "next_action": None
    })

run("Happy Path")
run("Optional Failure")
run("Critical Failure")