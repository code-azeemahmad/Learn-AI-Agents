import operator
from typing import Annotated, Literal

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

# ==========================================
# 1. State Schema & Failure Types
# ==========================================
FailureType = Literal[
    "transient",
    "invalid_plan",
    "missing_capability",
    "stale_plan",
    "dependency",
    "unrecoverable",
]

class Failure(TypedDict):
    type: FailureType
    message: str
    step: int | None

class State(TypedDict):
    user_task: str
    plan: list[str]
    current_step: int
    results: Annotated[list[str], operator.add]
    failure: Failure | None
    retry_count: int
    replan_count: int

MAX_RETRIES = 3
MAX_REPLANS = 2

# ==========================================
# 2. Nodes
# ==========================================
def planner(state: State):
    task = state["user_task"]
    replan_count = state.get("replan_count", 0)
    
    print(f"\n[Planner] Attempt {replan_count + 1} for task: '{task}'")
    
    # 💥 SIMULATION: Planner generates an invalid plan on the first try
    if "invalid" in task and replan_count == 0:
        print("  [Planner] ❌ Validation Error: Plan is missing required steps.")
        return {
            "failure": {"type": "invalid_plan", "message": "Empty plan generated.", "step": None},
            "replan_count": replan_count + 1
        }
        
    # Standard Plan Generation
    plan = ["Step A", "Step B"]
    if replan_count > 0:
        plan = ["Step C", "Step D"]  # The "Replanned" strategy
        
    return {
        "plan": plan, 
        "current_step": 0,
        "failure": None,  # Clear any previous failures
        "replan_count": replan_count + 1
    }

def executor(state: State):
    cursor = state["current_step"]
    task_str = state["user_task"]
    step_name = state["plan"][cursor]
    retry_count = state.get("retry_count", 0)
    
    print(f"  [Executor] Attempt {retry_count + 1} for Step {cursor}: {step_name}")
    
    # 💥 SIMULATION: Transient network failure (Timeout)
    if "transient" in task_str and cursor == 0 and retry_count < 2:
        print("  [Executor] ❌ Error: API Timeout")
        return {
            "failure": {"type": "transient", "message": "Timeout", "step": cursor},
            "retry_count": retry_count + 1
        }
        
    # 💥 SIMULATION: Stale plan discovered during execution
    if "stale" in task_str and cursor == 1:
        print("  [Executor] ❌ Error: The targeted API was deprecated!")
        return {
            "failure": {"type": "stale_plan", "message": "API deprecated", "step": cursor}
        }
        
    # 💥 SIMULATION: Unrecoverable authorization error
    if "unrecoverable" in task_str and cursor == 0:
        print("  [Executor] ❌ Error: Access Denied. Insufficient permissions.")
        return {
            "failure": {"type": "unrecoverable", "message": "Access Denied", "step": cursor}
        }
        
    # ✅ SUCCESS
    return {
        "results": [f"Completed: {step_name}"],
        "current_step": cursor + 1,
        "failure": None,
        "retry_count": 0  # Reset retries upon success
    }

# ==========================================
# 3. Recovery Router
# ==========================================
def recovery_router(state: State) -> Literal["planner", "executor", END]:
    failure = state.get("failure")
    
    if failure:
        err_type = failure["type"]
        
        # POLICY: Retries for transient mechanical errors
        if err_type == "transient":
            if state.get("retry_count", 0) <= MAX_RETRIES:
                print("  [Router] 🔄 Transient failure detected. Routing to EXECUTOR (Retry).")
                return "executor"
            else:
                print("  [Router] 🛑 Max retries exhausted. Halting.")
                return END
                
        # POLICY: Replans for strategic/validation errors
        if err_type in ["invalid_plan", "stale_plan", "missing_capability"]:
            # Note: replan_count tracks total planner calls, so max 2 replans = 3 calls
            if state.get("replan_count", 0) <= MAX_REPLANS:
                print(f"  [Router] 🔄 {err_type.upper()} detected. Routing to PLANNER (Replan).")
                return "planner"
            else:
                print("  [Router] 🛑 Max replans exhausted. Halting.")
                return END
                
        # POLICY: Hard stop for unrecoverable errors
        if err_type == "unrecoverable":
            print("  [Router] 🛑 Unrecoverable failure. Halting.")
            return END

    # No failures. Proceed with execution or terminate if complete.
    if state["current_step"] < len(state["plan"]):
        return "executor"
        
    print("  [Router] ✅ Plan complete. Routing to END.")
    return END

# ==========================================
# 4. Build & Compile Graph
# ==========================================
builder = StateGraph(State)

builder.add_node("planner", planner)
builder.add_node("executor", executor)

builder.add_edge(START, "planner")

# Both the Planner (invalid plans) and Executor (execution errors) 
# send their state to the Recovery Router to decide the next move.
builder.add_conditional_edges("planner", recovery_router)
builder.add_conditional_edges("executor", recovery_router)

graph = builder.compile()

# ==========================================
# 5. Test Driver
# ==========================================
def run_simulation(task: str):
    print(f"\n{'='*60}\nSCENARIO: {task}\n{'='*60}")
    graph.invoke({
        "user_task": task,
        "plan": [],
        "current_step": 0,
        "results": [],
        "failure": None,
        "retry_count": 0,
        "replan_count": 0
    })

run_simulation("Test invalid plan recovery")
run_simulation("Test transient timeout recovery")
run_simulation("Test stale plan recovery")
run_simulation("Test unrecoverable failure")