import uuid
from enum import Enum
from typing import Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph


# ==========================================
# 1. State & Server Mock
# ==========================================
class AgentState(TypedDict):
    scenario: str
    idempotency_key: str
    order_id: Optional[str]
    operation_status: Literal["pending", "success", "failed", "unknown"]
    retry_count: int

# Simulated Remote Database
# If a key exists here, the user has been charged!
REMOTE_DATABASE = {}

# ==========================================
# 2. Preparation Node
# ==========================================
def prepare_operation_node(state: AgentState):
    """Generates the unique logical ID for this operation."""
    # We only generate this ONCE. If we retry, we use the same key.
    key = state.get("idempotency_key")
    if not key:
        key = f"req-{uuid.uuid4().hex[:8]}"
        print(f"\n  [Preparation] Generated Idempotency Key: {key}")
        
    return {"idempotency_key": key, "operation_status": "pending"}

# ==========================================
# 3. Execution Node (The Dangerous Tool)
# ==========================================
def execute_write_node(state: AgentState):
    """Simulates charging a credit card and creating an order."""
    key = state["idempotency_key"]
    attempt = state.get("retry_count", 0) + 1
    
    print(f"\n  [Execution] Attempt {attempt} | Calling create_order API with key: {key}...")
    
    # 1. Server-Side Idempotency Check (The server protects itself)
    if key in REMOTE_DATABASE:
        print("    -> SERVER: Key already exists. Returning existing order. (Double-charge prevented!)")
        return {"operation_status": "success", "order_id": REMOTE_DATABASE[key], "retry_count": attempt}

    # 2. Simulate Scenarios
    if state["scenario"] == "Immediate Failure":
        print("    -> CLIENT: Network disconnected BEFORE request was sent.")
        return {"operation_status": "failed", "retry_count": attempt}
        
    if state["scenario"] == "Timeout (Order Exists)":
        if attempt == 1:
            # Server creates it, but client drops connection and doesn't know!
            REMOTE_DATABASE[key] = f"ORD-{uuid.uuid4().hex[:6]}"
            print("    -> CLIENT: HTTP 504 Gateway Timeout. (But server actually created the order!)")
            return {"operation_status": "unknown", "retry_count": attempt}
            
    if state["scenario"] == "Timeout (Order Absent)":
        if attempt == 1:
            print("    -> CLIENT: HTTP 504 Gateway Timeout. (Server died before processing request.)")
            return {"operation_status": "unknown", "retry_count": attempt}

    # 3. Happy Path
    order_id = f"ORD-{uuid.uuid4().hex[:6]}"
    REMOTE_DATABASE[key] = order_id
    print(f"    -> SERVER: Order {order_id} created successfully.")
    
    return {"operation_status": "success", "order_id": order_id, "retry_count": attempt}

# ==========================================
# 4. Recovery & Status Nodes
# ==========================================
def status_check_node(state: AgentState):
    """The critical step to resolve 'Unknown' states."""
    key = state["idempotency_key"]
    print("  [Status Check] Querying server to see if operation actually succeeded...")
    
    if key in REMOTE_DATABASE:
        print("    -> FOUND IT! The order was created. We can safely continue without retrying.")
        return {"operation_status": "success", "order_id": REMOTE_DATABASE[key]}
        
    print("    -> Not found. The server never processed the request. It is safe to retry.")
    return {"operation_status": "failed"}

def finalize_node(state: AgentState):
    if state["operation_status"] == "success":
        print(f"  [Finalize] Workflow complete. Order ID: {state['order_id']}")
    else:
        print("  [Finalize] Workflow aborted due to failure.")
    return {}

# ==========================================
# 5. Routing Logic
# ==========================================
def classify_outcome_router(state: AgentState) -> Literal["finalize", "retry_execution", "status_check", "__end__"]:
    status = state["operation_status"]
    
    if status == "success":
        return "finalize"
        
    if status == "unknown":
        print("  [Router] Outcome UNKNOWN. Routing to Status Check.")
        return "status_check"
        
    if status == "failed":
        if state["retry_count"] >= 2:
            print("  [Router] Max retries reached. Aborting.")
            return "finalize"
        print("  [Router] Definite failure detected. Safe to retry immediately.")
        return "retry_execution"
        
    return "__end__"

def post_check_router(state: AgentState) -> Literal["finalize", "retry_execution"]:
    # If the check found the order, we are done. If not, it switched the status to "failed", so we retry.
    if state["operation_status"] == "success":
        return "finalize"
    return "retry_execution"

# ==========================================
# 6. Build Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("prepare", prepare_operation_node)
builder.add_node("execute", execute_write_node)
builder.add_node("status_check", status_check_node)
builder.add_node("finalize", finalize_node)

builder.add_edge(START, "prepare")
builder.add_edge("prepare", "execute")

# Route based on the outcome of the execution
builder.add_conditional_edges("execute", classify_outcome_router, {
    "finalize": "finalize",
    "retry_execution": "execute",
    "status_check": "status_check",
    "__end__": END
})

# After checking status, either finalize or retry
builder.add_conditional_edges("status_check", post_check_router, {
    "finalize": "finalize",
    "retry_execution": "execute"
})

builder.add_edge("finalize", END)

graph = builder.compile()

# ==========================================
# 7. Execution Scenarios
# ==========================================
def run(scenario: str):
    print(f"\n\n{'='*60}\n=== SCENARIO: {scenario.upper()} ===\n{'='*60}")
    graph.invoke({"scenario": scenario, "idempotency_key": "", "order_id": None, "operation_status": "pending", "retry_count": 0})

# Happy Path
run("Success")

# Failed before sending. Safe to retry immediately.
run("Immediate Failure")

# The most dangerous path. Connection dropped, but server processed it.
run("Timeout (Order Exists)")

# Connection dropped, server died before processing.
run("Timeout (Order Absent)")