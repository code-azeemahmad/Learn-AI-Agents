import operator
from typing import Annotated, Literal

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict


# ==========================================
# 1. Define the Plan State
# ==========================================
class State(TypedDict):
    user_task: str
    plan: list[str]
    current_step: int  # The Execution Cursor
    results: Annotated[list[str], operator.add]

# ==========================================
# 2. Nodes
# ==========================================
def planner(state: State):
    print(f"\n[Planner] Creating execution plan for: '{state['user_task']}'")
    
    # Generate the sequential plan
    plan = [
        "Research Qdrant",
        "Research Pinecone",
        "Compare Qdrant and Pinecone",
        "Make recommendation"
    ]
    
    # Initialize the cursor to 0
    return {"plan": plan, "current_step": 0}

def executor(state: State):
    # Read the execution cursor
    cursor = state["current_step"]
    
    # Retrieve the specific task for this iteration
    current_task = state["plan"][cursor]
    
    # Debug prints required by the lesson
    print(f"  [Executor] Current step: {cursor}")
    print(f"  [Executor] Task: {current_task}")
    
    # Simulate execution
    simulated_result = f"Completed: {current_task}"
    
    # Update state: Append result, advance cursor
    return {
        "results": [simulated_result],
        "current_step": cursor + 1
    }

# ==========================================
# 3. Router
# ==========================================
def route(state: State) -> Literal["executor", END]:
    # Check if the cursor has reached the end of the plan
    if state["current_step"] < len(state["plan"]):
        return "executor"
    
    print("  [Router] No steps remaining. Routing to END.")
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

graph = builder.compile()

# ==========================================
# 5. Execution Test
# ==========================================
print("=== Starting Planner/Executor Workflow ===")
initial_state = {
    "user_task": "Compare vector databases",
    "plan": [],
    "current_step": 0,
    "results": []
}

final_state = graph.invoke(initial_state)

print("\n=== Final State ===")
for key, value in final_state.items():
    print(f"{key}: {value}")