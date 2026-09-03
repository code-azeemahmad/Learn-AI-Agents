from typing import Dict, List, Literal, Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


# ==========================================
# 1. State Schema
# ==========================================
class AgentState(TypedDict):
    scenario: str
    proposed_action: dict
    status: str

# ==========================================
# 2. Application Domain: Users & Policies
# ==========================================
# Simulated enterprise directory
USERS = {
    "alice_emp": {"name": "Alice", "role": "employee", "tenant_id": "Tenant-A"},
    "bob_mgr": {"name": "Bob", "role": "manager", "tenant_id": "Tenant-A"},
    "carol_fin": {"name": "Carol", "role": "finance_manager", "tenant_id": "Tenant-A"},
    "dave_fin": {"name": "Dave", "role": "finance_manager", "tenant_id": "Tenant-B"}
}

# The Hardcoded Security Policy
TOOL_POLICIES = {
    "search_documents": {"risk": "low", "required_role": "automatic"},
    "send_email": {"risk": "medium", "required_role": "employee"},
    "delete_document": {"risk": "high", "required_role": "manager"},
    "delete_finance_document": {"risk": "critical", "required_role": "finance_manager"}
}

class ApprovalRouter:
    def determine_required_role(self, action_name: str) -> str:
        policy = TOOL_POLICIES.get(action_name, {"required_role": "admin"})
        return policy["required_role"]

    def find_eligible_approvers(self, tenant_id: str, required_role: str) -> List[str]:
        """Finds all users in the correct tenant who have the exact required role."""
        eligible = []
        for user_id, data in USERS.items():
            if data["tenant_id"] == tenant_id and data["role"] == required_role:
                eligible.append(user_id)
        return eligible

router = ApprovalRouter()
db_approvals = {} # Simulated PostgreSQL table

# ==========================================
# 3. LangGraph Nodes
# ==========================================
def agent_node(state: AgentState):
    print(f"\n{'='*60}\n[Scenario]: {state['scenario']}")
    action = state["proposed_action"]
    print(f"  [Agent] Proposing Action: {action['name']} on resource '{action.get('target', 'N/A')}'")
    return {"status": "pending_approval"}

def hitl_node(state: AgentState):
    """The graph pauses here and waits for the backend to route and resolve the approval."""
    print("  [System] Interrupting execution. Waiting for secure backend resume...")
    
    # We yield the exact action payload. The backend will read this to figure out routing.
    decision = interrupt(state["proposed_action"])
    
    print(f"  [System] Woke up! Backend provided decision: {decision['decision'].upper()}")
    return {"status": decision["decision"]}

def execute_node(state: AgentState):
    if state["status"] == "approve":
        print("  [Execution] Running Side Effect!")
    else:
        print("  [Execution] Action Rejected.")
    return {}

# ==========================================
# 4. Build Graph
# ==========================================
builder = StateGraph(AgentState)
builder.add_node("agent", agent_node)
builder.add_node("hitl", hitl_node)
builder.add_node("execute", execute_node)

builder.add_edge(START, "agent")
builder.add_edge("agent", "hitl")
builder.add_edge("hitl", "execute")
builder.add_edge("execute", END)

memory = MemorySaver()
graph = builder.compile(checkpointer=memory)

# ==========================================
# 5. Backend Application APIs
# ==========================================
def api_start_workflow(thread_id: str, scenario: str, requester_id: str, action: dict):
    """Starts the graph, intercepts the pause, and dynamically routes the approval."""
    config = {"configurable": {"thread_id": thread_id}}
    requester = USERS[requester_id]
    initial_state = {"scenario": scenario, "proposed_action": action, "status": "pending"}
    
    for event in graph.stream(initial_state, config):
        pass # Stream to interrupt
        
    paused_state = graph.get_state(config)
    action_payload = paused_state.tasks[0].interrupts[0].value
    
    # 1. Routing Logic (Backend determines WHO can approve)
    required_role = router.determine_required_role(action_payload["name"])
    
    if required_role == "automatic":
        print("  [Backend] Action is LOW RISK. Auto-resuming graph...")
        graph.invoke(Command(resume={"decision": "approve"}), config)
        return
        
    eligible_approvers = router.find_eligible_approvers(requester["tenant_id"], required_role)
    
    # 2. Create the Database Record
    approval_id = f"app-{thread_id}"
    db_approvals[approval_id] = {
        "thread_id": thread_id,
        "tenant_id": requester["tenant_id"],
        "requester_id": requester_id,
        "required_role": required_role,
        "eligible_approvers": eligible_approvers,
        "status": "pending"
    }
    
    print(f"  [Backend] Created Approval Record '{approval_id}'.")
    print(f"    -> Requires Role: '{required_role}'. Eligible Approvers: {eligible_approvers}")

def api_resolve_approval(approval_id: str, responding_user_id: str, decision: str):
    """The endpoint the human UI hits when they click Approve/Reject."""
    print(f"\n  [Backend API] User '{responding_user_id}' is attempting to resolve '{approval_id}'...")
    
    record = db_approvals.get(approval_id)
    responder = USERS.get(responding_user_id)
    
    # 1. Security: Is the user eligible?
    if responding_user_id not in record["eligible_approvers"]:
        print(f"    -> 403 Forbidden: User '{responder['name']}' (Role: {responder['role']}, Tenant: {responder['tenant_id']}) is NOT authorized to approve this action.")
        return
        
    # 2. Security: No Self-Approval (Optional business logic)
    if responding_user_id == record["requester_id"]:
        print(f"    -> 403 Forbidden: You cannot approve your own request!")
        return
        
    print("    -> Security Checks Passed. Resuming LangGraph thread...")
    record["status"] = decision
    
    config = {"configurable": {"thread_id": record["thread_id"]}}
    graph.invoke(Command(resume={"decision": decision}), config)

# ==========================================
# 6. Run Scenarios
# ==========================================

# Scenario 1: Alice wants to delete a finance doc. Carol (Finance Mgr in Tenant A) approves.
api_start_workflow("thread-1", "Happy Path", "alice_emp", {"name": "delete_finance_document", "target": "q3_report.pdf"})
api_resolve_approval("app-thread-1", "carol_fin", "approve")

# Scenario 2: Alice tries to approve her OWN request (even though she's not a Finance Mgr anyway)
api_start_workflow("thread-2", "Self-Approval Attack", "alice_emp", {"name": "delete_finance_document", "target": "q3_report.pdf"})
api_resolve_approval("app-thread-2", "alice_emp", "approve")

# Scenario 3: Dave is a Finance Mgr, but he belongs to Tenant B! He tries to approve Tenant A's doc.
api_start_workflow("thread-3", "Cross-Tenant Attack", "alice_emp", {"name": "delete_finance_document", "target": "q3_report.pdf"})
api_resolve_approval("app-thread-3", "dave_fin", "approve")

# Scenario 4: Bob is a Manager in Tenant A. But this is a FINANCE doc, requiring a Finance Manager.
api_start_workflow("thread-4", "Role Escalation Attack", "alice_emp", {"name": "delete_finance_document", "target": "q3_report.pdf"})
api_resolve_approval("app-thread-4", "bob_mgr", "approve")