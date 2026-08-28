from typing import List

from typing_extensions import TypedDict


# 1. Define PlanStep
class PlanStep(TypedDict):
    id: int
    task: str
    dependencies: List[int]

# 2. Manually mock the dependency-aware plan
plan: List[PlanStep] = [
    {"id": 1, "task": "Research Qdrant for multi-tenant RAG capabilities", "dependencies": []},
    {"id": 2, "task": "Research pgvector for multi-tenant RAG capabilities", "dependencies": []},
    {"id": 3, "task": "Research Milvus for multi-tenant RAG capabilities", "dependencies": []},
    {"id": 4, "task": "Compare Qdrant, pgvector, and Milvus based on research", "dependencies": [1, 2, 3]},
    {"id": 5, "task": "Recommend the best vector database", "dependencies": [4]},
]

# 3. Helper function to simulate execution order
def print_execution_order(plan: List[PlanStep]):
    print("=== Execution Simulator ===")
    
    # We will track which tasks are completed
    completed_ids = set()
    layer = 1
    
    while len(completed_ids) < len(plan):
        current_layer_tasks = []
        
        # Find all tasks whose dependencies are met and haven't been completed yet
        for step in plan:
            if step["id"] not in completed_ids:
                # Check if all dependencies are in completed_ids
                if all(dep in completed_ids for dep in step["dependencies"]):
                    current_layer_tasks.append(step)
                    
        # Print the current layer
        print(f"\n[Layer {layer}: Parallel Execution]")
        for task in current_layer_tasks:
            print(f"  -> Executing Task {task['id']}: {task['task']}")
            
        # Mark tasks in this layer as completed
        for task in current_layer_tasks:
            completed_ids.add(task["id"])
            
        layer += 1

print_execution_order(plan)