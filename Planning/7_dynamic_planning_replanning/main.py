import operator
from typing import Annotated, Literal

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict


# ==========================================
# 1. State Schema
# ==========================================
class State(TypedDict):
    user_task: str
    plan: list[str]
    current_step: int
    results: Annotated[list[str], operator.add]
    needs_replan: bool
    replan_count: int

# ==========================================
# 2. Nodes
# ==========================================
def planner(state: State):
    replan_count = state.get("replan_count", 0)
    
    if replan_count == 0:
        print(f"\n[Planner] Generating INITIAL plan for: '{state['user_task']}'")
        plan = [
            "Research A",
            "Research B",
            "Compare"
        ]
    else:
        print(f"\n[Planner] REPLANNING (Revision {replan_count}). Generating updated plan...")
        plan = [
            "Research C",
            "Recompare",
            "Recommend"
        ]
        
    return {
        "plan": plan,
        "current_step": 0,           # Reset cursor for the new plan
        "needs_replan": False,       # Reset the flag
        "replan_count": replan_count + 1
    }

def executor(state: State):
    cursor = state["current_step"]
    task = state["plan"][cursor]
    
    print(f"  [Executor] Step {cursor}: {task}")
    
    return {
        "results": [f"Executed: {task}"],
        "current_step": cursor + 1
    }

def evaluator(state: State):
    # Simulate an environment check: 
    # After "Research B" (which increments cursor to 2), we discover the plan is flawed.
    # We also check replan_count == 1 so we only trigger this interruption once.
    if state["replan_count"] == 1 and state["current_step"] == 2:
        print("  [Evaluator] WAIT! New information discovered. The current plan is invalid.")
        return {"needs_replan": True}
    
    print("  [Evaluator] Plan is still valid.")
    return {"needs_replan": False}

# ==========================================
# 3. Router
# ==========================================
def route(state: State) -> Literal["planner", "executor", END]:
    # 1. Check for strategic failure (Replanning)
    if state["needs_replan"]:
        # Safety Boundary: Prevent infinite replanning loops
        if state["replan_count"] <= 2:
            print("  [Router] Routing to Planner.")
            return "planner"
        else:
            print("  [Router] Max replans reached. Halting execution.")
            return END
            
    # 2. Check for normal continuation
    if state["current_step"] < len(state["plan"]):
        return "executor"
        
    # 3. Successful termination
    print("  [Router] Plan complete. Routing to END.")
    return END

# ==========================================
# 4. Build & Compile Graph
# ==========================================
builder = StateGraph(State)

builder.add_node("planner", planner)
builder.add_node("executor", executor)
builder.add_node("evaluator", evaluator)

builder.add_edge(START, "planner")
builder.add_edge("planner", "executor")
builder.add_edge("executor", "evaluator")

# The Evaluator feeds into the conditional Router
builder.add_conditional_edges(
    "evaluator",
    route,
    {"planner": "planner", "executor": "executor", END: END}
)

graph = builder.compile()

# ==========================================
# 5. Execution Test
# ==========================================
print("=== Starting Dynamic Planning Workflow ===")
initial_state = {
    "user_task": "Evaluate database landscape",
    "plan": [],
    "current_step": 0,
    "results": [],
    "needs_replan": False,
    "replan_count": 0
}

final_state = graph.invoke(initial_state)

print("\n=== Final State ===")
print(f"Total Replans: {final_state['replan_count'] - 1}")
print("Accumulated Results:")
for res in final_state['results']:
    print(f"  - {res}")