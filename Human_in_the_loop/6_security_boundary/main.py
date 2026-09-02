from typing import Literal, Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel


# ==========================================
# 1. State Schema
# ==========================================
class AgentState(TypedDict):
    scenario: str
    target_document: str
    tenant_id: str
    status: str

# ==========================================
# 2. Graph Nodes
# ==========================================
def prepare_action_node(state: AgentState):
    print(f"\n{'='*60}\n[Scenario]: {state['scenario']}")
    print(f"  [Agent] Proposing deletion of '{state['target_document']}' in tenant '{state['tenant_id']}'.")
    return {"status": "pending_approval"}

def approval_node(state: AgentState):
    """The graph pauses here, trusting the backend to only resume it safely."""
    print("  [Agent] Pausing execution. Waiting for secure backend resume...")
    
    # We yield the exact action fingerprint so the backend knows what is pending
    decision = interrupt({
        "type": "delete_document",
        "document": state["target_document"],
        "tenant": state["tenant_id"]
    })
    
    # If the backend resumed us, it means all security checks passed!
    print(f"  [Agent] Resumed securely! Backend provided decision: {decision['action']}")
    return {"status": decision["action"]}

def execute_node(state: AgentState):
    if state["status"] == "approved":
        print(f"  [Agent] DELETING document '{state['target_document']}'...")
    else:
        print(f"  [Agent] Action rejected. Aborting.")
    return {}

# ==========================================
# 3. Build Graph
# ==========================================
builder = StateGraph(AgentState)
builder.add_node("prepare", prepare_action_node)
builder.add_node("approval", approval_node)
builder.add_node("execute", execute_node)

builder.add_edge(START, "prepare")
builder.add_edge("prepare", "approval")
builder.add_edge("approval", "execute")
builder.add_edge("execute", END)

memory = MemorySaver()
graph = builder.compile(checkpointer=memory)

# ==========================================
# 4. The Backend Security API (The real lesson)
# ==========================================
class BackendApprovalDatabase:
    """Simulates an external database tracking pending approvals."""
    def __init__(self):
        self.records = {}

db = BackendApprovalDatabase()

def backend_start_workflow(thread_id: str, scenario: str, tenant_id: str):
    """Starts the graph and registers the pending approval in the backend DB."""
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {"scenario": scenario, "target_document": "financial_q3_report.pdf", "tenant_id": tenant_id, "status": "pending"}
    
    for event in graph.stream(initial_state, config):
        pass # Stream to the interrupt
        
    paused_state = graph.get_state(config)
    interrupt_data = paused_state.tasks[0].interrupts[0].value
    
    # Register the approval in the secure backend database
    approval_id = f"app-{thread_id}"
    db.records[approval_id] = {
        "thread_id": thread_id,
        "tenant_id": tenant_id,
        "action_fingerprint": interrupt_data["document"],
        "status": "pending" # Prevents replay attacks
    }
    print(f"  [Backend] Workflow paused. Approval record '{approval_id}' created in database.")

def backend_resume_api_handler(approval_id: str, requesting_user: dict, frontend_payload: dict):
    """
    This simulates a POST /approvals/{id}/decision endpoint.
    Notice how many checks happen before we touch LangGraph.
    """
    print(f"\n  [Backend API] Received request to resolve approval '{approval_id}' by {requesting_user['name']}...")
    
    record = db.records.get(approval_id)
    
    # 1. Validation Layer
    if not record:
        print("    -> 404: Approval record not found.")
        return
        
    # 2. Replay Attack Prevention
    if record["status"] != "pending":
        print("    -> 400: Replay Attack! This approval has already been consumed.")
        return
        
    # 3. Tenant Isolation Layer (Authorization)
    if requesting_user["tenant_id"] != record["tenant_id"]:
        print(f"    -> 403: Cross-Tenant Attack! User '{requesting_user['name']}' belongs to '{requesting_user['tenant_id']}', but approval is for '{record['tenant_id']}'.")
        return
        
    # 4. Role-Based Access Control (Authorization)
    if requesting_user["role"] != "manager":
        print(f"    -> 403: Insufficient Privileges. User '{requesting_user['name']}' is a '{requesting_user['role']}'. Deletion requires 'manager'.")
        return
        
    # 5. Action Binding (Preventing Malicious Edits)
    if frontend_payload.get("target_document") != record["action_fingerprint"]:
        print(f"    -> 400: Malicious Edit Detected! The frontend tried to approve '{frontend_payload.get('target_document')}' but the agent proposed '{record['action_fingerprint']}'.")
        return
        
    # 6. Execute Resume (Only after all 5 checks pass!)
    print("    -> Backend Security Checks Passed. Resuming LangGraph thread...")
    record["status"] = "consumed" # Consume the token
    
    config = {"configurable": {"thread_id": record["thread_id"]}}
    graph.invoke(Command(resume={"action": frontend_payload["decision"]}), config)

# ==========================================
# 5. Run Scenarios
# ==========================================
backend_start_workflow("thread-A", "Happy Path", "Tenant-1")
backend_resume_api_handler(
    approval_id="app-thread-A", 
    requesting_user={"name": "Alice", "role": "manager", "tenant_id": "Tenant-1"}, 
    frontend_payload={"decision": "approve", "target_document": "financial_q3_report.pdf"}
)

backend_start_workflow("thread-B", "Cross Tenant Attack", "Tenant-2")
backend_resume_api_handler(
    approval_id="app-thread-B", 
    requesting_user={"name": "Bob", "role": "manager", "tenant_id": "Tenant-1"}, # Bob is a manager, but wrong tenant! 
    frontend_payload={"decision": "approve", "target_document": "financial_q3_report.pdf"}
)

backend_start_workflow("thread-C", "Role Attack", "Tenant-1")
backend_resume_api_handler(
    approval_id="app-thread-C", 
    requesting_user={"name": "Charlie", "role": "intern", "tenant_id": "Tenant-1"}, # Charlie is right tenant, but an intern!
    frontend_payload={"decision": "approve", "target_document": "financial_q3_report.pdf"}
)

# REPLAY ATTACK TEST
# Let's try to submit Alice's approval (from thread-A) a second time!
backend_resume_api_handler(
    approval_id="app-thread-A", 
    requesting_user={"name": "Alice", "role": "manager", "tenant_id": "Tenant-1"}, 
    frontend_payload={"decision": "approve", "target_document": "financial_q3_report.pdf"}
)