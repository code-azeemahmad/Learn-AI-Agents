from typing import Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

# ==========================================
# 1. State Schema & Constraints
# ==========================================
MAX_TOOL_CALLS = 2

class AgentState(TypedDict):
    scenario: str
    evidence_sufficient: bool
    tool_calls: int
    revisions: int
    cost: float
    latency: float

# ==========================================
# 2. Nodes
# ==========================================
def gather_evidence_node(state: AgentState):
    """Simulates retrieving evidence. Adds to the cost/latency budget."""
    print(f"\n{'='*50}\n[Scenario]: {state['scenario']}")
    print("  [Tool] Gathering evidence... (Cost: $0.01 | Latency: 1.5s)")
    
    cost = state.get("cost", 0.0) + 0.01
    latency = state.get("latency", 0.0) + 1.5
    tool_calls = state.get("tool_calls", 0) + 1
    
    # Simulate finding sufficient evidence immediately on the first try for Scenario A
    sufficient = state["scenario"] == "Easy Question"
    
    return {"cost": cost, "latency": latency, "tool_calls": tool_calls, "evidence_sufficient": sufficient}

def reason_node(state: AgentState):
    """Simulates the LLM reasoning. Adds to the cost/latency budget."""
    print("  [Reasoner] Processing data... (Cost: $0.03 | Latency: 3.0s)")
    return {"cost": state["cost"] + 0.03, "latency": state["latency"] + 3.0}

def revise_node(state: AgentState):
    """Simulates the LLM revising. Adds to the cost/latency budget."""
    print("  [Reviser] Fixing missing data... (Cost: $0.04 | Latency: 4.0s)")
    return {"cost": state["cost"] + 0.04, "latency": state["latency"] + 4.0, "evidence_sufficient": True}

# ==========================================
# 3. Routers
# ==========================================
def early_exit_router(state: AgentState) -> Literal["reason", "gather_evidence", "__end__"]:
    """
    OPTIMIZATION 1: The Early Exit.
    If we have the data, skip the extra tool calls and go straight to reasoning.
    """
    # OPTIMIZATION 2: The Hard Budget
    if state["tool_calls"] >= MAX_TOOL_CALLS:
        print(f"  [Router] HARD BUDGET REACHED ({MAX_TOOL_CALLS} tool calls). Forcing exit to save money.")
        return "__end__"
        
    if state["evidence_sufficient"]:
        print("  [Router] EARLY EXIT: Evidence is sufficient. Skipping extra retrieval loops.")
        return "reason"
        
    print("  [Router] Evidence insufficient. Routing back for more data.")
    return "gather_evidence"

# ==========================================
# 4. Build Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("gather_evidence", gather_evidence_node)
builder.add_node("reason", reason_node)
builder.add_node("revise", revise_node)

builder.add_edge(START, "gather_evidence")

# The Router evaluates the state and triggers the Early Exit or the Budget Cutoff
builder.add_conditional_edges("gather_evidence", early_exit_router)

# After reasoning, we simulate needing a revision if it wasn't an easy question
def route_after_reason(state: AgentState):
    if state["scenario"] == "Hard Question": return "revise"
    return "__end__"
    
builder.add_conditional_edges("reason", route_after_reason)
builder.add_edge("revise", END)

graph = builder.compile()

# ==========================================
# 5. Execution Scenarios
# ==========================================
def run_scenario(scenario_name: str):
    final_state = graph.invoke({
        "scenario": scenario_name, "evidence_sufficient": False, 
        "tool_calls": 0, "revisions": 0, "cost": 0.0, "latency": 0.0
    })
    print(f"  FINAL METRICS -> Cost: ${final_state['cost']:.2f} | Latency: {final_state['latency']}s")

run_scenario("Easy Question")
run_scenario("Hard Question")
run_scenario("Impossible Question")