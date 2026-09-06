import json
from datetime import datetime
from typing import Literal, Optional, TypedDict

from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import END, START, StateGraph


# ==========================================
# 1. State Schema & Audit Mocks
# ==========================================
class AgentState(TypedDict):
    scenario: str
    proposed_tool: str
    proposed_args: dict
    final_output: str

# Simulated append-only Audit Database
AUDIT_LOG = []

def emit_security_event(event_type: str, severity: str, user: str, tenant: str, tool: str, decision: str, reason: str):
    """Writes a structured Security Event to the Immutable Audit Log."""
    event = {
        "timestamp": datetime.now().isoformat(),
        "event_type": event_type,
        "severity": severity,
        "actor": {"user_id": user, "tenant_id": tenant},
        "action": {"tool": tool},
        "policy_decision": decision,
        "reason": reason
    }
    AUDIT_LOG.append(event)
    print(f"    [Audit Service] Logged Security Event: {event_type} ({decision})")

# ==========================================
# 2. Nodes
# ==========================================
def llm_node(state: AgentState):
    """Simulates the LLM proposing a tool call."""
    print(f"\n{'='*60}\n[Scenario]: {state['scenario']}")
    
    if state["scenario"] == "Cross-Tenant Attack":
        return {"proposed_tool": "read_document", "proposed_args": {"doc_id": "999", "target_tenant": "tenant-B"}}
        
    elif state["scenario"] == "Safe Request":
        return {"proposed_tool": "read_document", "proposed_args": {"doc_id": "101", "target_tenant": "tenant-A"}}

def authz_node(state: AgentState, config: RunnableConfig):
    """
    The Authorization Node. 
    Crucially, it logs its decisions to the Audit Service.
    """
    tool = state["proposed_tool"]
    args = state["proposed_args"]
    
    tenant_id = config["configurable"]["tenant_id"]
    user_id = config["configurable"]["user_id"]
    
    print(f"  [AuthZ] Evaluating request...")
    
    # Check 1: Tenant Violation
    if args.get("target_tenant") != tenant_id:
        print("    -> AUTHZ BLOCKED: Cross-Tenant Violation.")
        
        # THE SECURITY BOUNDARY: We explicitly emit a High-Severity Audit Event
        emit_security_event(
            event_type="cross_tenant_attempt",
            severity="CRITICAL",
            user=user_id,
            tenant=tenant_id,
            tool=tool,
            decision="DENY",
            reason=f"Attempted to access {args.get('target_tenant')}"
        )
        return {"final_output": "Execution Denied."}
        
    # Check 2: Safe Execution
    print("    -> AuthZ Passed.")
    emit_security_event(
        event_type="tool_execution",
        severity="INFO",
        user=user_id,
        tenant=tenant_id,
        tool=tool,
        decision="ALLOW",
        reason="RBAC and ABAC checks passed."
    )
    return {"final_output": f"Executed {tool} successfully."}

# ==========================================
# 3. Build Graph
# ==========================================
builder = StateGraph(AgentState)
builder.add_node("llm", llm_node)
builder.add_node("authz", authz_node)

builder.add_edge(START, "llm")
builder.add_edge("llm", "authz")
builder.add_edge("authz", END)

graph = builder.compile()

# ==========================================
# 4. Backend API
# ==========================================
def run_scenario(scenario: str):
    config = {"configurable": {"tenant_id": "tenant-A", "user_id": "alice_admin"}}
    initial_state = {"scenario": scenario, "proposed_tool": "", "proposed_args": {}, "final_output": ""}
    
    graph.invoke(initial_state, config=config)

run_scenario("Safe Request")
run_scenario("Cross-Tenant Attack")

print(f"\n{'='*60}\n[SYSTEM AUDIT LOG DUMP]")
print(json.dumps(AUDIT_LOG, indent=2))