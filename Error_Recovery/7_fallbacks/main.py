from typing import Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel


# ==========================================
# 1. Output Contracts & State
# ==========================================
class SearchResult(BaseModel):
    documents: list[str]
    source: str
    degraded: bool

class AgentState(TypedDict):
    scenario: str
    current_tenant: str  # System-enforced security boundary
    query: str
    results: Optional[dict]
    error_type: Optional[str]
    next_action: Optional[Literal["fallback", "abort", "finish"]]

# ==========================================
# 2. Nodes
# ==========================================
def primary_search_node(state: AgentState):
    """Primary Capability: High-quality Semantic Hybrid Search."""
    print(f"\n  [Primary] Executing Semantic Hybrid Search for tenant: '{state['current_tenant']}'...")
    
    if state["scenario"] in ["Primary Outage", "Total Outage"]:
        print("    -> 503: Vector Database (Qdrant) Unreachable.")
        return {"error_type": "vector_db_unavailable"}
        
    print("    -> Success: Semantic match found.")
    res = SearchResult(documents=["Doc_A_Semantic", "Doc_B_Semantic"], source="Hybrid Search API", degraded=False)
    return {"results": res.model_dump(), "error_type": None}

def classifier_node(state: AgentState):
    """Determines if the error warrants a fallback or an immediate abort."""
    print(f"  [Classifier] Analyzing failure: {state['error_type']}")
    
    if state["error_type"] == "vector_db_unavailable":
        print("    -> Action: FALLBACK to relational database.")
        return {"next_action": "fallback"}
        
    print("    -> Action: ABORT.")
    return {"next_action": "abort"}

def fallback_search_node(state: AgentState):
    """Fallback Capability: Basic Keyword Search in PostgreSQL."""
    print(f"  [Fallback] Executing Basic Keyword Search for tenant: '{state['current_tenant']}'...")
    
    if state["scenario"] == "Total Outage":
        print("    -> 500: Relational Database (PostgreSQL) Unreachable.")
        return {"error_type": "total_infrastructure_failure"}
        
    print("    -> Success (Degraded): Keyword match found.")
    
    # CRITICAL: The fallback must respect the same output contract as the primary!
    res = SearchResult(documents=["Doc_A_Keyword"], source="PostgreSQL Text Search", degraded=True)
    return {"results": res.model_dump(), "error_type": None}

def handle_result_node(state: AgentState):
    """Downstream node consumes the result blindly, relying on the Capability Contract."""
    res = SearchResult(**state["results"])
    status = "[DEGRADED MODE] " if res.degraded else ""
    print(f"  [Output] {status}Retrieved {len(res.documents)} documents via {res.source}.")
    return {"next_action": "finish"}

# ==========================================
# 3. Routers
# ==========================================
def route_primary(state: AgentState) -> Literal["classifier", "handle_result"]:
    if state.get("error_type"):
        return "classifier"
    return "handle_result"

def route_classifier(state: AgentState) -> Literal["fallback_search", "__end__"]:
    if state["next_action"] == "fallback":
        return "fallback_search"
    print("  [Router] Fatal error. Aborting workflow.")
    return "__end__"

def route_fallback(state: AgentState) -> Literal["handle_result", "__end__"]:
    if state.get("error_type"):
        print("  [Router] Fallback failed. Total system outage. Aborting.")
        return "__end__"
    return "handle_result"

# ==========================================
# 4. Build Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("primary_search", primary_search_node)
builder.add_node("classifier", classifier_node)
builder.add_node("fallback_search", fallback_search_node)
builder.add_node("handle_result", handle_result_node)

builder.add_edge(START, "primary_search")

# Primary -> Success or Classifier
builder.add_conditional_edges("primary_search", route_primary)

# Classifier -> Fallback or Abort
builder.add_conditional_edges("classifier", route_classifier)

# Fallback -> Success or Abort
builder.add_conditional_edges("fallback_search", route_fallback)

builder.add_edge("handle_result", END)

graph = builder.compile()

# ==========================================
# 5. Execution Scenarios
# ==========================================
def run(scenario: str):
    print(f"\n\n{'='*60}\n=== SCENARIO: {scenario.upper()} ===\n{'='*60}")
    graph.invoke({
        "scenario": scenario, "current_tenant": "tenant-42", "query": "auth policies",
        "results": None, "error_type": None, "next_action": None
    })

run("Happy Path")
run("Primary Outage")
run("Total Outage")