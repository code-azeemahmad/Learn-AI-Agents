from typing import Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel


# ==========================================
# 1. State & Structured Output Schemas
# ==========================================
class AgentState(TypedDict):
    scenario: str
    evidence: list[str]
    search_budget: int
    decision: Optional[str]
    next_action: Optional[str]
    error: Optional[str]

# The strict contract we expect from the LLM
class EvaluationDecision(BaseModel):
    next_action: Literal["search", "verify", "finish"]
    reason: str

# ==========================================
# 2. Nodes
# ==========================================
def gather_evidence_node(state: AgentState):
    print(f"\n[Scenario]: {state['scenario']}")
    
    if state["scenario"] == "Insufficient Evidence":
        evidence = ["Fact: Qdrant supports filtering."]
    elif state["scenario"] == "Enough Evidence":
        evidence = [
            "Req: Requires filtering.", "Req: Requires hybrid retrieval.",
            "Fact: Qdrant supports filtering.", "Fact: Qdrant supports hybrid retrieval."
        ]
    elif state["scenario"] == "Budget Exhausted":
        evidence = ["Fact: Qdrant supports filtering."] # Same as insufficient, but budget is 0
        
    print("  [Data] Initial Evidence:")
    for e in evidence:
        print(f"    - {e}")
        
    return {"evidence": evidence}

def reason_node(state: AgentState):
    """
    Simulates: llm.with_structured_output(EvaluationDecision).invoke(evidence)
    """
    print("  [Reasoner] Evaluating evidence against requirements...")
    evidence_str = str(state["evidence"])
    
    # Simulating the LLM returning the structured Pydantic object
    if "hybrid retrieval" not in evidence_str:
        decision = EvaluationDecision(
            next_action="search",
            reason="We need evidence about the remaining workload requirements (hybrid retrieval)."
        )
    else:
        decision = EvaluationDecision(
            next_action="verify",
            reason="The evidence supports the conclusion, but capabilities should be verified against authoritative sources."
        )
        
    print(f"  -> Structured Output: next_action='{decision.next_action}', reason='{decision.reason}'")
    
    return {"next_action": decision.next_action, "decision": decision.reason}

def validation_layer_node(state: AgentState):
    """
    CRITICAL: The LLM does not get the final say. 
    The application validates the LLM's requested action against business logic.
    """
    requested_action = state["next_action"]
    print(f"  [Validator] Checking if requested action '{requested_action}' is allowed...")
    
    if requested_action == "search" and state["search_budget"] <= 0:
        print("    VALIDATION FAILED: Search budget exhausted! Overriding LLM.")
        return {"next_action": "finish", "error": "Aborted: Search budget exhausted before conclusion could be reached."}
        
    print("    VALIDATION PASSED: Action allowed.")
    return {"error": None}

# Mock destination nodes
def search_node(state: AgentState):
    print("  [Action] Executing Search...")
def verify_node(state: AgentState):
    print("  [Action] Executing Verification...")

# ==========================================
# 3. Router
# ==========================================
def deterministic_router(state: AgentState) -> Literal["search", "verify", "__end__"]:
    """
    The router is completely dumb. It just reads the validated string.
    """
    if state["next_action"] == "search":
        return "search"
    elif state["next_action"] == "verify":
        return "verify"
    return "__end__"

# ==========================================
# 4. Build & Execute Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("gather_evidence", gather_evidence_node)
builder.add_node("reason", reason_node)
builder.add_node("validate", validation_layer_node)
builder.add_node("search", search_node)
builder.add_node("verify", verify_node)

builder.add_edge(START, "gather_evidence")
builder.add_edge("gather_evidence", "reason")
builder.add_edge("reason", "validate")

# The router ONLY fires AFTER validation
builder.add_conditional_edges("validate", deterministic_router)

# In a real app, these would loop back to `reason`. We end here for the demo.
builder.add_edge("search", END)
builder.add_edge("verify", END)

graph = builder.compile()

# ==========================================
# 5. Execution Scenarios
# ==========================================
print("=== STRUCTURED REASONING SIMULATION ===")

# Test 1
graph.invoke({"scenario": "Insufficient Evidence", "search_budget": 5, "evidence": []})

# Test 2
graph.invoke({"scenario": "Enough Evidence", "search_budget": 5, "evidence": []})

# Test 3: The Validation Override
final_state = graph.invoke({"scenario": "Budget Exhausted", "search_budget": 0, "evidence": []})
if final_state.get("error"):
    print(f"  FINAL STATE: {final_state['error']}")