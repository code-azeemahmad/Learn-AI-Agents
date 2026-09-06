from typing import Literal, Optional, TypedDict

from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import END, START, StateGraph


# ==========================================
# 1. State Schema
# ==========================================
class AgentState(TypedDict):
    scenario: str
    
    # Untrusted LLM Request
    proposed_tool: str
    proposed_args: dict
    
    final_output: str

# Simulated Database of Resources
DATABASE = {
    "doc_101": {"tenant_id": "tenant-A", "content": "Acme Financials"},
    "doc_999": {"tenant_id": "tenant-B", "content": "Globex Secrets"}
}

# ==========================================
# 2. Nodes
# ==========================================
def llm_node(state: AgentState):
    """
    Simulates the LLM proposing a tool call.
    In the Confused Deputy scenario, the LLM is tricked into acting on behalf of a guest!
    """
    print(f"\n{'='*60}\n[Scenario]: {state['scenario']}")
    
    # We hardcode the LLM proposals to test the AuthZ layer
    if state["scenario"] == "Admin Deletes Own File":
        return {"proposed_tool": "delete_document", "proposed_args": {"doc_id": "doc_101"}}
        
    elif state["scenario"] == "Guest Attempts Deletion (Confused Deputy)":
        return {"proposed_tool": "delete_document", "proposed_args": {"doc_id": "doc_101"}}
        
    elif state["scenario"] == "Admin Cross-Tenant Attack (ABAC check)":
        return {"proposed_tool": "delete_document", "proposed_args": {"doc_id": "doc_999"}}

def authorization_node(state: AgentState, config: RunnableConfig):
    """
    The Policy Engine. It evaluates the RBAC and ABAC rules before allowing execution.
    """
    tool = state["proposed_tool"]
    args = state["proposed_args"]
    
    # 1. Extract Trusted Identity Context
    tenant_id = config["configurable"]["tenant_id"]
    user_role = config["configurable"]["user_role"]
    
    print(f"  [AuthZ] Evaluating: {tool}({args})")
    print(f"  [AuthZ] Trusted Identity -> Role: {user_role} | Tenant: {tenant_id}")
    
    if tool == "delete_document":
        doc_id = args["doc_id"]
        
        # --- 2. RBAC Check (Role-Based Access Control) ---
        if user_role != "admin":
            print(f"    -> AUTHZ BLOCKED: Confused Deputy Attack! Agent has system rights, but User '{user_role}' lacks permission.")
            return {"final_output": "Execution Denied: RBAC Violation."}
            
        # --- 3. ABAC Check (Attribute-Based Access Control) ---
        # Fetch the actual resource from the DB to check ownership
        resource = DATABASE.get(doc_id)
        if not resource:
            return {"final_output": "Execution Denied: Resource not found."}
            
        if resource["tenant_id"] != tenant_id:
            print(f"    -> AUTHZ BLOCKED: Cross-Tenant Breach! Admin in '{tenant_id}' tried to access resource in '{resource['tenant_id']}'.")
            return {"final_output": "Execution Denied: ABAC Tenant Violation."}
            
        # --- 4. Execution ---
        print("    -> AuthZ Passed! Both RBAC and ABAC conditions met. Executing deletion.")
        return {"final_output": f"Successfully deleted {doc_id}."}

# ==========================================
# 3. Build Graph
# ==========================================
builder = StateGraph(AgentState)
builder.add_node("llm", llm_node)
builder.add_node("authz", authorization_node)

builder.add_edge(START, "llm")
builder.add_edge("llm", "authz")
builder.add_edge("authz", END)
graph = builder.compile()

# ==========================================
# 4. Backend Execution API
# ==========================================
def secure_api_handler(scenario: str, user_role: str, tenant_id: str):
    config = {
        "configurable": {"tenant_id": tenant_id, "user_role": user_role}
    }
    initial_state = {"scenario": scenario, "proposed_tool": "", "proposed_args": {}, "final_output": ""}
    
    final_state = graph.invoke(initial_state, config=config)
    print(f"  [System Output]: {final_state['final_output']}")

# Scenarios
# 1. Admin safely deleting a file in their own tenant
secure_api_handler("Admin Deletes Own File", user_role="admin", tenant_id="tenant-A")

# 2. A Guest tricks the LLM into initiating a delete. The LLM falls for it, but AuthZ blocks it!
secure_api_handler("Guest Attempts Deletion (Confused Deputy)", user_role="guest", tenant_id="tenant-A")

# 3. An Admin from Tenant A tries to delete a file belonging to Tenant B!
secure_api_handler("Admin Cross-Tenant Attack (ABAC check)", user_role="admin", tenant_id="tenant-A")