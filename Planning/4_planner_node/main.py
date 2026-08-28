import operator
from typing import Annotated, Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel
from typing_extensions import TypedDict


# ==========================================
# 1. Structured Output Schema
# ==========================================
class Plan(BaseModel):
    steps: list[str]

# ==========================================
# 2. State Schema
# ==========================================
class State(TypedDict):
    user_task: str
    plan: list[str]
    current_step: int
    results: Annotated[list[str], operator.add]

# ==========================================
# 3. Setup LLM & Planner Chain
# ==========================================
llm = ChatOllama(model="gemma4:26b", temperature=0)

# Bind the Pydantic schema to the model
structured_llm = llm.with_structured_output(Plan)

planner_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a task planner. 
Break the user's task into a small number of clear, executable steps.

Rules:
- Each step must represent meaningful work.
- Avoid implementation-level micro-steps.
- Preserve the user's constraints.
- Create only the steps necessary to complete the task.
- Maximum 6 steps."""),
    ("human", "Task: {task}")
])

planner_chain = planner_prompt | structured_llm

# ==========================================
# 4. Nodes
# ==========================================
def planner_node(state: State):
    task = state["user_task"]
    print(f"\n[Planner] Analyzing task: '{task}'")
    
    # 1. Generate Structured Plan
    plan_obj = planner_chain.invoke({"task": task})
    
    # 2. Application-Level Validation (Enforcing limits)
    if not plan_obj.steps:
        raise ValueError("Planner returned no steps.")
        
    if len(plan_obj.steps) > 6:
        raise ValueError(f"Planner returned too many steps ({len(plan_obj.steps)}). Maximum allowed is 6.")
    
    # 3. Print the raw plan to inspect quality
    print("[Planner] Generated and Validated Plan:")
    for index, step in enumerate(plan_obj.steps, start=1):
        print(f"  {index}. {step}")
        
    # Return exactly what the Executor needs
    return {
        "plan": plan_obj.steps,
        "current_step": 0
    }

def executor_node(state: State):
    cursor = state["current_step"]
    current_task = state["plan"][cursor]
    
    print(f"  [Executor] Step {cursor + 1}: {current_task}")
    
    # Simulate the work
    simulated_result = f"Completed: {current_task}"
    
    return {
        "results": [simulated_result],
        "current_step": cursor + 1
    }

# ==========================================
# 5. Router
# ==========================================
def route(state: State) -> Literal["executor", END]:
    if state["current_step"] < len(state["plan"]):
        return "executor"
    
    print("  [Router] Plan complete. Routing to END.")
    return END

# ==========================================
# 6. Build & Compile Graph
# ==========================================
builder = StateGraph(State)

builder.add_node("planner", planner_node)
builder.add_node("executor", executor_node)

builder.add_edge(START, "planner")
builder.add_edge("planner", "executor")

builder.add_conditional_edges(
    "executor",
    route,
    {"executor": "executor", END: END}
)

graph = builder.compile()

# ==========================================
# 7. Execution Tests
# ==========================================
def run_test(query: str):
    print(f"\n{'='*60}\nTESTING: {query}\n{'='*60}")
    try:
        graph.invoke({
            "user_task": query,
            "plan": [],
            "current_step": 0,
            "results": []
        })
    except Exception as e:
        print(f"[Error Blocked Execution] {e}")

# Test 1: Simple Task
run_test("Calculate the average of three numbers.")

# Test 2: Medium Task
run_test("Compare Qdrant and Pinecone for a RAG application.")

# Test 3: Complex Task (Will test the 6-step limit)
run_test("Design a production architecture for a multi-tenant RAG assistant with authentication, Qdrant retrieval, streaming, evaluation, and observability.")