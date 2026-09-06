from typing import Literal, Optional, TypedDict

from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import END, START, StateGraph


# ==========================================
# 1. State Schema
# ==========================================
class AgentState(TypedDict):
    scenario: str
    
    # LLM Output
    proposed_query: str
    
    # Execution Output
    final_output: str

# Simulated Database
DATABASE = [
    {"id": 1, "tenant_id": "tenant-A", "data": "Acme Q3 Revenue: $1M"},
    {"id": 2, "tenant_id": "tenant-A", "data": "Acme Q4 Revenue: $1.2M"},
    {"id": 3, "tenant_id": "tenant-B", "data": "BetaCorp Secret Payroll: $500k"},
]

# ==========================================
# 2. Nodes
# ==========================================
def agent_node(state: AgentState):
    """Simulates an LLM generating a SQL query."""
    print(f"\n{'='*60}\n[Scenario]: {state['scenario']}")
    
    if state["scenario"] == "Honest Query":
        # The LLM doesn't even know its own tenant ID. It just asks for the data.
        query = "SELECT data FROM database"
    elif state["scenario"] == "Malicious Cross-Tenant Query":
        # The LLM was hijacked and tries to steal BetaCorp's data
        query = "SELECT data FROM database WHERE tenant_id = 'tenant-B'"
        
    print(f"  [Agent] Generated Query: '{query}'")
    return {"proposed_query": query}

def execute_sql_node(state: AgentState, config: RunnableConfig):
    """
    The Data Access Tool. It enforces Mandatory Tenant Scoping.
    It NEVER trusts the LLM's WHERE clause regarding tenant identity.
    """
    trusted_tenant = config["configurable"]["tenant_id"]
    llm_query = state["proposed_query"]
    
    print(f"  [DB Tool] Intercepting query. Applying Mandatory Scope: tenant_id='{trusted_tenant}'")
    
    # Simulate a SQL engine applying a mandatory row-level security policy
    results = []
    for row in DATABASE:
        # 🛡️ THE SECURITY BOUNDARY: We only return rows that match the TRUSTED context
        if row["tenant_id"] == trusted_tenant:
            # If the LLM tried to filter for Tenant B, we just ignore it or it naturally yields 0 results.
            # Here, we simulate executing the query but bounded by the tenant lock.
            if "tenant-B" in llm_query:
                # The LLM asked for B, but we are locked to A. The intersection is empty.
                pass 
            else:
                results.append(row["data"])
                
    if not results and "tenant-B" in llm_query:
         return {"final_output": "0 rows returned. (Cross-tenant query yielded no results within authorized scope)."}

    return {"final_output": f"Success. Retrieved {len(results)} rows: {results}"}

# ==========================================
# 3. Build Graph
# ==========================================
builder = StateGraph(AgentState)
builder.add_node("agent", agent_node)
builder.add_node("execute_sql", execute_sql_node)

builder.add_edge(START, "agent")
builder.add_edge("agent", "execute_sql")
builder.add_edge("execute_sql", END)

graph = builder.compile()

# ==========================================
# 4. Backend Execution API
# ==========================================
def secure_api_handler(scenario: str, tenant_id: str):
    # The Backend establishes the Trusted Context
    config = {"configurable": {"tenant_id": tenant_id}}
    
    final_state = graph.invoke({"scenario": scenario, "proposed_query": "", "final_output": ""}, config=config)
    print(f"  [System Output]: {final_state['final_output']}")


# 1. Honest query from Acme
secure_api_handler("Honest Query", tenant_id="tenant-A")

# 2. Acme's LLM tries to steal BetaCorp's data
secure_api_handler("Malicious Cross-Tenant Query", tenant_id="tenant-A")