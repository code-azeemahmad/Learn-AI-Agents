from typing import Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ValidationError

# ==========================================
# 1. State & Output Schemas
# ==========================================
MAX_REPAIRS = 2

class SearchInput(BaseModel):
    query: str
    top_k: int
class AgentState(TypedDict):
    scenario: str
    current_tenant: str
    tool_args: dict
    validation_error: Optional[str]
    status: Literal["pending", "valid", "invalid_repairable", "forbidden", "success", "aborted"]
    repair_count: int

# ==========================================
# 2. Nodes
# ==========================================
def generate_tool_call_node(state: AgentState):
    """Simulates the LLM attempting to call a tool based on the scenario."""
    attempt = state.get("repair_count", 0) + 1
    print(f"\n  [LLM] Generating tool arguments... (Attempt {attempt})")
    
    if state["scenario"] == "Valid Call":
        args = {"query": "authentication", "top_k": 5}
        
    elif state["scenario"] == "Missing Argument":
        if attempt == 1:
            args = {"query": "authentication"} # Missing top_k
        else:
            args = {"query": "authentication", "top_k": 5} # Repaired
            
    elif state["scenario"] == "Business Violation":
        if attempt == 1:
            args = {"query": "authentication", "top_k": 5000} # Exceeds max 50
        else:
            args = {"query": "authentication", "top_k": 50} # Repaired
            
    elif state["scenario"] == "Unauthorized":
        # Simulating a malicious or hallucinated cross-tenant query
        args = {"query": "authentication", "top_k": 5, "tenant_id": "tenant-B"}
        
    elif state["scenario"] == "Infinite Loop":
        args = {"query": "authentication"} # Never learns
        
    print(f"    -> LLM Output: {args}")
    return {"tool_args": args}

def validate_tool_call_node(state: AgentState):
    """The 3-Layer Defensive Boundary."""
    print("  [Validator] Inspecting tool call...")
    args = state["tool_args"]
    
    # LAYER 1: Schema Validation (Pydantic)
    try:
        # We only pass query and top_k to Pydantic. It ignores extras.
        SearchInput(**{k:v for k,v in args.items() if k in ['query', 'top_k']})
    except ValidationError as exc:
        err = f"Schema Error: {exc.errors()[0]['msg']}"
        print(f"    {err}")
        return {"status": "invalid_repairable", "validation_error": err}
        
    # LAYER 2: Business Validation
    if not (1 <= args.get("top_k", 0) <= 50):
        err = "Business Error: top_k must be between 1 and 50."
        print(f"    {err}")
        return {"status": "invalid_repairable", "validation_error": err}
        
    # LAYER 3: Authorization Validation
    # We check if the LLM tried to inject a tenant_id that doesn't belong to it
    if args.get("tenant_id") and args.get("tenant_id") != state["current_tenant"]:
        err = f"Auth Error: Cannot access data for {args['tenant_id']}. You are {state['current_tenant']}."
        print(f"    SECURITY VIOLATION: {err}")
        return {"status": "forbidden", "validation_error": err}
        
    print("    VALIDATION PASSED. Ready for execution.")
    return {"status": "valid", "validation_error": None}

def repair_node(state: AgentState):
    """Feeds the validation error back to the LLM state."""
    count = state.get("repair_count", 0) + 1
    print(f"  [Repair] Instructing LLM to fix error: '{state['validation_error']}'")
    return {"repair_count": count}

def execute_tool_node(state: AgentState):
    """Executes the actual tool now that it is guaranteed safe."""
    print("  [Execution] Running tool safely...")
    return {"status": "success"}

# ==========================================
# 3. Router
# ==========================================
def validation_router(state: AgentState) -> Literal["execute_tool", "repair", "__end__"]:
    status = state["status"]
    
    if status == "valid":
        return "execute_tool"
        
    if status == "forbidden":
        print("  [Router] Unauthorized action. Failing closed.")
        return "__end__"
        
    if status == "invalid_repairable":
        if state["repair_count"] >= MAX_REPAIRS:
            print("  [Router] Max repairs reached. Aborting to prevent infinite loop.")
            return "__end__"
        return "repair"
        
    return "__end__"

# ==========================================
# 4. Build Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("generate_tool_call", generate_tool_call_node)
builder.add_node("validate", validate_tool_call_node)
builder.add_node("repair", repair_node)
builder.add_node("execute_tool", execute_tool_node)

builder.add_edge(START, "generate_tool_call")
builder.add_edge("generate_tool_call", "validate")

builder.add_conditional_edges("validate", validation_router)

builder.add_edge("repair", "generate_tool_call")
builder.add_edge("execute_tool", END)

graph = builder.compile()

# ==========================================
# 5. Execution Scenarios
# ==========================================
def run(scenario: str):
    print(f"\n\n{'='*50}\n=== SCENARIO: {scenario.upper()} ===\n{'='*50}")
    graph.invoke({"scenario": scenario, "current_tenant": "tenant-A", "tool_args": {}, "status": "pending", "repair_count": 0})

run("Valid Call")
run("Missing Argument")
run("Business Violation")
run("Unauthorized")
run("Infinite Loop")