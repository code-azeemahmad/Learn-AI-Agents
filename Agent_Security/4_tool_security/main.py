from typing import Literal, Optional, TypedDict

from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import END, START, StateGraph


# ==========================================
# 1. State Schema
# ==========================================
class AgentState(TypedDict):
    scenario: str
    user_query: str
    
    # LLM Output (Untrusted)
    proposed_tool: Optional[str]
    proposed_args: Optional[dict]
    
    final_output: str

# ==========================================
# 2. Nodes
# ==========================================
def llm_node(state: AgentState):
    """
    Simulates the LLM proposing a tool call based on the scenario.
    This output is fundamentally untrusted.
    """
    print(f"\n{'='*60}\n[Scenario]: {state['scenario']}")
    
    if state["scenario"] == "Safe Read":
        return {"proposed_tool": "get_policy", "proposed_args": {"topic": "refunds"}}
        
    elif state["scenario"] == "Safe Write":
        return {"proposed_tool": "refund_order", "proposed_args": {"order_id": "123", "amount": 50, "target_tenant": "tenant-A"}}
        
    elif state["scenario"] == "Untrusted LLM Payload":
        # The LLM hallucinates or is tricked into targeting another tenant's data
        return {"proposed_tool": "refund_order", "proposed_args": {"order_id": "999", "amount": 50, "target_tenant": "tenant-B"}}
        
    elif state["scenario"] == "Policy Violation":
        return {"proposed_tool": "refund_order", "proposed_args": {"order_id": "123", "amount": 5000, "target_tenant": "tenant-A"}}

def tool_gateway_node(state: AgentState, config: RunnableConfig):
    """
    The Defense-in-Depth Pipeline. 
    Intercepts the proposed tool call and applies strict security rules.
    """
    tool = state["proposed_tool"]
    args = state.get("proposed_args", {})
    
    # Extract Trusted Context (Injected by Application API)
    tenant_id = config["configurable"]["tenant_id"]
    user_role = config["configurable"]["user_role"]
    
    print(f"  [Tool Gateway] Processing Request: {tool}()")
    print(f"  [Tool Gateway] Trusted Context -> Tenant: {tenant_id} | Role: {user_role}")
    
    # --- 1. Schema Validation (Simulated) ---
    if not isinstance(args.get("amount", 0), (int, float)):
        return {"final_output": "Gateway Error: 'amount' must be a number."}
        
    # --- 2. Identity / Tenant Check ---
    if tool == "refund_order":
        # NEVER trust the LLM's target_tenant. Always validate against trusted context.
        if args.get("target_tenant") != tenant_id:
            print(f"    -> GATEWAY BLOCKED: Cross-Tenant Violation! LLM attempted to target {args.get('target_tenant')}.")
            return {"final_output": "Execution Denied: Cross-Tenant Access Prohibited."}
            
    # --- 3. Permission (RBAC) Check ---
    if tool == "refund_order" and user_role == "guest":
        print(f"    -> GATEWAY BLOCKED: Guests cannot execute refunds.")
        return {"final_output": "Execution Denied: Insufficient Privileges."}
        
    # --- 4. Risk Policy Check ---
    if tool == "refund_order":
        if args.get("amount", 0) > 1000 and user_role != "admin":
            print(f"    -> GATEWAY BLOCKED: Policy Violation! Support role cannot refund > $1000.")
            return {"final_output": "Execution Denied: Amount exceeds role limits. HITL required."}
            
    # --- 5. Execute ---
    print("    -> All Gateway Checks Passed. Executing Side Effect.")
    return {"final_output": f"Successfully executed {tool}."}

# ==========================================
# 3. Build Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("llm", llm_node)
builder.add_node("tool_gateway", tool_gateway_node)

builder.add_edge(START, "llm")
builder.add_edge("llm", "tool_gateway")
builder.add_edge("tool_gateway", END)

graph = builder.compile()

# ==========================================
# 4. Backend Execution API
# ==========================================
def secure_api_handler(scenario: str, user_role: str, tenant_id: str):
    config = {
        "configurable": {
            "tenant_id": tenant_id,
            "user_role": user_role
        }
    }
    
    initial_state = {
        "scenario": scenario, "user_query": "Dummy query",
        "proposed_tool": None, "proposed_args": None, "final_output": ""
    }
    
    final_state = graph.invoke(initial_state, config=config)
    print(f"  [System Output]: {final_state['final_output']}")

# Scenarios
# 1. Safe read
secure_api_handler("Safe Read", user_role="support", tenant_id="tenant-A")

# 2. Safe write within policy limits
secure_api_handler("Safe Write", user_role="support", tenant_id="tenant-A")

# 3. LLM tries to execute a refund for a different company!
secure_api_handler("Untrusted LLM Payload", user_role="support", tenant_id="tenant-A")

# 4. Support tries to refund $5,000, which exceeds the policy threshold
secure_api_handler("Policy Violation", user_role="support", tenant_id="tenant-A")