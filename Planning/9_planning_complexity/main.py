from typing import Literal

# ==========================================
# 1. Execution Modes
# ==========================================
ExecutionMode = Literal["direct", "static_plan", "dynamic_plan"]

# ==========================================
# 2. Complexity Classifier (The Router)
# ==========================================
def choose_execution_mode(task: str) -> ExecutionMode:
    """
    Evaluates the complexity and uncertainty of a user task 
    to route it to the cheapest, most effective architecture.
    """
    task_lower = task.lower()
    
    # HIGH UNCERTAINTY: Requires adaptation and environment discovery
    if "investigate" in task_lower or "root cause" in task_lower or "why" in task_lower:
        return "dynamic_plan"
        
    # MODERATE COMPLEXITY: Known multi-step structure, predictable path
    if "build" in task_lower or "api" in task_lower or "report" in task_lower:
        return "static_plan"
        
    # LOW COMPLEXITY: Simple facts, math, or single-tool queries
    return "direct"

# ==========================================
# 3. Execution Simulation
# ==========================================
def simulate_routing(task: str):
    print(f"\nTask: '{task}'")
    
    mode = choose_execution_mode(task)
    
    if mode == "direct":
        print("  -> Routing to: [DIRECT EXECUTION]")
        print("     (Fastest. LLM -> Tool -> Answer. No planning overhead.)")
        
    elif mode == "static_plan":
        print("  -> Routing to: [STATIC PLAN]")
        print("     (Moderate. Planner -> Sequential Executor. Good for known workflows.)")
        
    elif mode == "dynamic_plan":
        print("  -> Routing to: [DYNAMIC PLAN]")
        print("     (Expensive. Planner -> Executor -> Evaluator. High uncertainty.)")

# ==========================================
# 4. Tests
# ==========================================
print("=== Complexity Routing Simulation ===")

# Task A: Simple
simulate_routing("What's 25 × 37?")

# Task B: Moderate
simulate_routing("Build a product REST API with authentication.")

# Task C: Complex/Uncertain
simulate_routing("Investigate why our production API is slow and determine the root cause.")