import operator
from typing import Annotated, Literal

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict


# ==========================================
# 1. Structured State Schemas
# ==========================================
class StepResult(TypedDict):
    step_id: int
    status: Literal["completed", "failed"]
    output: str | None
    error: str | None

class State(TypedDict):
    user_task: str
    plan: list[str]
    current_step: int
    results: Annotated[list[StepResult], operator.add]  # reducer

# ==========================================
# 2. Simulated Capability (The "Tool")
# ==========================================
def execute_step(step: str) -> str:
    """Simulates an external capability (API, DB, LLM, etc.)"""
    if "Pinecone" in step:
        # Simulate a mechanical failure (e.g., API timeout)
        raise RuntimeError("Connection timeout to Pinecone API")
        
    return f"Successfully processed: {step}"

# ==========================================
# 3. Nodes
# ==========================================
def planner(state: State):
    print(f"\n[Planner] Creating plan for: '{state['user_task']}'")
    plan = [
        "Research Qdrant",
        "Research Pinecone",
        "Compare databases",
        "Recommend database"
    ]
    return {"plan": plan, "current_step": 0}

def executor(state: State):
    current_step = state["current_step"]
    step_task = state["plan"][current_step]
    
    print(f"  [Executor] Attempting Step {current_step}: {step_task}")
    
    try:
        # 1. Attempt the work
        output = execute_step(step_task)
        
        # 2. Return success structure AND advance cursor
        success_result = StepResult(
            step_id=current_step,
            status="completed",
            output=output,
            error=None
        )
        return {
            "results": [success_result],
            "current_step": current_step + 1
        }
        
    except Exception as exc:
        print(f"  [Executor] FAILED: {exc}")
        
        # 2. Return failure structure (DO NOT ADVANCE CURSOR)
        failure_result = StepResult(
            step_id=current_step,
            status="failed",
            output=None,
            error=str(exc)
        )
        return {
            "results": [failure_result]
            # Notice we omit "current_step". The cursor stays pointing at the failed step.
        }

# ==========================================
# 4. Router
# ==========================================
def route(state: State) -> Literal["executor", END]:
    # Check for failure first. 
    # If the last result was a failure, we must halt (for now).
    if state["results"] and state["results"][-1]["status"] == "failed":
        print("  [Router] Failure detected. Halting execution to prevent infinite loop.")
        return END

    # If successful, check if more steps remain
    if state["current_step"] < len(state["plan"]):
        return "executor"
    
    print("  [Router] Plan complete. Routing to END.")
    return END

# ==========================================
# 5. Build & Compile Graph
# ==========================================
builder = StateGraph(State)

builder.add_node("planner", planner)
builder.add_node("executor", executor)

builder.add_edge(START, "planner")
builder.add_edge("planner", "executor")

builder.add_conditional_edges(
    "executor",
    route,
    {"executor": "executor", END: END}
)

graph = builder.compile()

# ==========================================
# 6. Execution Test
# ==========================================
print("=== Starting Planner/Executor Workflow ===")
final_state = graph.invoke({
    "user_task": "Compare vector databases",
    "plan": [],
    "current_step": 0,
    "results": []
})

print("\n=== Final State Results ===")
for res in final_state["results"]:
    print(f"Step {res['step_id']} ({res['status']}): {res['output'] or res['error']}")