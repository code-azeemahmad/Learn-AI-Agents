from typing import Literal, TypedDict

from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.store.memory import InMemoryStore


# ==========================================
# 1. State Schema
# ==========================================
class AgentState(TypedDict):
    scenario: str
    user_query: str
    
    # These will be populated from the long-term Store
    relevant_tenant_memory: list[str]
    relevant_user_memory: list[str]
    
    final_output: str

# ==========================================
# 2. Setup Long-Term Store
# ==========================================
store = InMemoryStore()

# Pre-populate the Store with some facts
# Tenant A Shared Memory
store.put(("tenant-a", "shared"), "policy_1", {"fact": "Company policy requires 2-factor authentication."})
# Tenant B Shared Memory
store.put(("tenant-b", "shared"), "policy_1", {"fact": "Company policy allows guest logins."})

# Alice's Private Memory
store.put(("tenant-a", "user-alice", "private"), "pref_1", {"fact": "User prefers concise answers."})

# ==========================================
# 3. Nodes
# ==========================================
# FIXED: We explicitly type `config` as `RunnableConfig` so LangGraph knows to inject it!
def load_memory_node(state: AgentState, config: RunnableConfig):
    """
    This node intercepts the execution, reads the secure context injected by the backend,
    and searches the exact namespaces for long-term memory.
    """
    # 1. Extract secure context provided by the backend API
    # The LLM cannot fake this. It is hard-coded into the execution context.
    tenant_id = config["configurable"]["tenant_id"]
    user_id = config["configurable"]["user_id"]
    
    print(f"\n{'='*60}\n[Scenario]: {state['scenario']}")
    print(f"  [Memory Node] Authenticated Context -> Tenant: {tenant_id} | User: {user_id}")
    
    # 2. Search Tenant Shared Memory
    print(f"  [Memory Node] Searching Namespace: ('{tenant_id}', 'shared')")
    tenant_results = store.search((tenant_id, "shared"))
    tenant_facts = [item.value["fact"] for item in tenant_results]
    
    # 3. Search User Private Memory
    print(f"  [Memory Node] Searching Namespace: ('{tenant_id}', '{user_id}', 'private')")
    user_results = store.search((tenant_id, user_id, "private"))
    user_facts = [item.value["fact"] for item in user_results]
    
    return {
        "relevant_tenant_memory": tenant_facts,
        "relevant_user_memory": user_facts
    }

def synthesis_node(state: AgentState):
    """The Agent uses the retrieved long-term memory to answer the query."""
    print("  [Agent] Generating response using isolated context...")
    
    output = f"Answer based on memory:\n"
    output += f"  - Tenant Context: {state.get('relevant_tenant_memory')}\n"
    output += f"  - User Context: {state.get('relevant_user_memory')}"
    
    return {"final_output": output}

# ==========================================
# 4. Build Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("load_memory", load_memory_node)
builder.add_node("synthesis", synthesis_node)

builder.add_edge(START, "load_memory")
builder.add_edge("load_memory", "synthesis")
builder.add_edge("synthesis", END)

# We pass the store into the compiled graph so the nodes can access it via the `config` context
graph = builder.compile(store=store)

# ==========================================
# 5. Backend Execution APIs
# ==========================================
def secure_api_handler(scenario: str, requesting_user: str, target_tenant: str):
    """
    Simulates the FastAPI endpoint. It defines the identity configuration 
    BEFORE calling LangGraph.
    """
    # The secure context injection!
    config = {
        "configurable": {
            "tenant_id": target_tenant,
            "user_id": requesting_user,
            "thread_id": "thread-123" # Checkpointer ID (short-term)
        }
    }
    
    # Initialize the state fully so the typed dict is complete
    initial_state = {
        "scenario": scenario, 
        "user_query": "What are my policies?",
        "relevant_tenant_memory": [],
        "relevant_user_memory": [],
        "final_output": ""
    }
    
    final_state = graph.invoke(initial_state, config=config)
    print(f"  [System Output]:\n{final_state['final_output']}")


# Scenarios
# 1. Alice queries her own tenant
secure_api_handler("Alice (Tenant A)", requesting_user="user-alice", target_tenant="tenant-a")

# 2. Bob queries his own tenant (Same company as Alice)
secure_api_handler("Bob (Tenant A)", requesting_user="user-bob", target_tenant="tenant-a")

# 3. Charlie queries his own tenant (Different company)
secure_api_handler("Charlie (Tenant B)", requesting_user="user-charlie", target_tenant="tenant-b")