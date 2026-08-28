import operator
from typing import Annotated, Literal

from langgraph.checkpoint.memory import InMemorySaver
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

# ==========================================
# 2. Nodes
# ==========================================
def planner(state: State):
    print(f"\n[Planner] Generating static plan for: '{state['user_task']}'")
    
    plan = [
        "Collect information",
        "Analyze information",
        "Create summary"
    ]
    
    return {"plan": plan, "current_step": 0}

def executor(state: State):
    cursor = state["current_step"]
    current_task = state["plan"][cursor]
    
    # Observe how we can read previous results to inform the current step
    previous_results_count = len(state.get("results", []))
    
    print(f"  [Executor] Step {cursor + 1}: {current_task} (Context: {previous_results_count} prior results)")
    
    simulated_result = f"Completed: {current_task}"
    
    return {
        "results": [simulated_result],
        "current_step": cursor + 1
    }

# ==========================================
# 3. Router
# ==========================================
def route(state: State) -> Literal["executor", END]:
    if state["current_step"] < len(state["plan"]):
        return "executor"
    
    print("  [Router] Execution complete. Routing to END.")
    return END

# ==========================================
# 4. Build & Compile Graph
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

# Attach the Checkpointer for persistence
checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)

# ==========================================
# 5. Execution Test
# ==========================================
print("=== Starting Stateful Sequential Workflow ===")

# Define the execution thread
config = {"configurable": {"thread_id": "planning-demo-123"}}

initial_state = {
    "user_task": "Write a report on LangGraph",
    "plan": [],
    "current_step": 0,
    "results": []
}

# Run the graph
final_state = graph.invoke(initial_state, config)

print("\n=== Final Checkpointed State ===")
for key, value in final_state.items():
    print(f"{key}: {value}")