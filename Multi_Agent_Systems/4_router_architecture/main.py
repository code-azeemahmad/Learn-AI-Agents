from typing import List, Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field


# ==========================================
# 1. State Schema & Pydantic Route
# ==========================================
class AgentState(TypedDict):
    scenario: str
    user_request: str
    
    # Notice we don't have complex 'research_result' or 'sql_result' 
    # Because the router just dispatches and doesn't synthesize!
    route_decision: str
    final_output: Optional[str]

# We force the LLM to output one of these EXACT strings
ALLOWED_ROUTES = Literal["knowledge", "sql", "billing", "fallback"]

class RouteDecision(BaseModel):
    destination: ALLOWED_ROUTES = Field(description="The specialist agent to handle the request.")
    reason: str = Field(description="A brief explanation of why this route was chosen.")

# ==========================================
# 2. Router Node (Simulated LLM)
# ==========================================
def llm_router_node(state: AgentState):
    """
    Simulates an LLM calling `model.with_structured_output(RouteDecision)`.
    It makes a single, one-shot classification.
    """
    request = state["user_request"].lower()
    print(f"\n{'='*60}\n[User]: {state['user_request']}")
    print("  [LLM Router] Classifying request intent...")
    
    # Simulate the LLM's classification logic
    if "invoice" in request or "refund" in request:
        decision = RouteDecision(destination="billing", reason="User is asking about financial billing operations.")
    elif "how many" in request or "metrics" in request or "database" in request:
        decision = RouteDecision(destination="sql", reason="User is asking for quantitative data requiring a database query.")
    elif "policy" in request or "docs" in request:
        decision = RouteDecision(destination="knowledge", reason="User is asking about internal company documentation.")
    elif state["scenario"] == "LLM Hallucination":
        # Simulating an LLM failure where validation fails
        print("  [LLM Router] LLM returned invalid JSON or hallucinated a route!")
        return {"route_decision": "fallback"}
    else:
        decision = RouteDecision(destination="fallback", reason="The request is ambiguous or out of scope.")
        
    print(f"  [LLM Router] Decision: {decision.destination.upper()} | Reason: {decision.reason}")
    return {"route_decision": decision.destination}

# ==========================================
# 3. Specialist Nodes (The Dispatch Targets)
# ==========================================
def knowledge_agent_node(state: AgentState):
    print("    [Knowledge Agent] Accessing Qdrant Vector DB...")
    return {"final_output": "According to the HR docs, parental leave is 12 weeks."}

def sql_agent_node(state: AgentState):
    print("    [SQL Agent] Executing COUNT(*) query on PostgreSQL...")
    return {"final_output": "There are 42 active employees in the HR department."}

def billing_agent_node(state: AgentState):
    print("    [Billing Agent] Accessing Stripe API...")
    return {"final_output": "Invoice #102 is currently processing."}

def fallback_node(state: AgentState):
    """The critical safety net for bad routes or ambiguous questions."""
    print("    [Fallback] Request is out of bounds or routing failed.")
    return {"final_output": "I'm sorry, I'm not sure how to help with that. Could you clarify your request?"}

# ==========================================
# 4. Routing Edge Logic
# ==========================================
def route_dispatch(state: AgentState) -> str:
    """A clean, explicit map of string outputs to graph nodes."""
    decision = state["route_decision"]
    
    # Safety Check: If it's not a recognized route, force fallback!
    valid_routes = {"knowledge", "sql", "billing"}
    if decision not in valid_routes:
        return "fallback"
        
    return decision

# ==========================================
# 5. Build Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("router", llm_router_node)

# Add all our specialists
builder.add_node("knowledge", knowledge_agent_node)
builder.add_node("sql", sql_agent_node)
builder.add_node("billing", billing_agent_node)
builder.add_node("fallback", fallback_node)

builder.add_edge(START, "router")

# The Router dictates the ONE path the graph will take
builder.add_conditional_edges("router", route_dispatch)

# Notice how ALL specialists immediately go to END. 
# There is NO loop back to the router!
builder.add_edge("knowledge", END)
builder.add_edge("sql", END)
builder.add_edge("billing", END)
builder.add_edge("fallback", END)

graph = builder.compile()

# ==========================================
# 6. Execution Scenarios
# ==========================================
def run(scenario: str, query: str):
    final_state = graph.invoke({"scenario": scenario, "user_request": query})
    print(f"  [Final Result]: {final_state.get('final_output')}")

run("Knowledge Route", "What is the parental leave policy?")
run("SQL Route", "How many employees are in HR?")
run("Billing Route", "I need a refund for my invoice.")
run("Ambiguous Request", "What is the meaning of life?")
run("LLM Hallucination", "Show me the logs.")