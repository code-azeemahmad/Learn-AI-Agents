import operator
from typing import Annotated, Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel


# ==========================================
# 1. State & Output Schemas
# ==========================================
class AgentState(TypedDict):
    scenario: str
    question: str
    requirements: list[str]
    evidence: Annotated[list[str], operator.add]
    evidence_sufficient: bool
    contradictions_found: bool
    conclusion: Optional[str]
    verified: bool

class EvidenceAssessment(BaseModel):
    sufficient: bool
    contradictions: list[str]
    missing_data: list[str]
    action: Literal["reason", "retrieve"]

# ==========================================
# 2. Simulated Retrieval Tools
# ==========================================
def retrieve_evidence(scenario: str, loop_count: int) -> list[str]:
    """Simulates a RAG pipeline or Search API."""
    print("  [Tool] Retrieving external evidence...")
    
    if scenario == "Sufficient Evidence":
        return ["Docs(2026): Qdrant supports metadata filtering and hybrid retrieval natively."]
        
    elif scenario == "Insufficient Evidence":
        if loop_count == 0:
            return ["Docs(2026): Qdrant supports metadata filtering."] # Missing hybrid
        else:
            return ["Docs(2026): Qdrant also supports hybrid retrieval."] # Found on retry
            
    elif scenario == "Contradictory Evidence":
        if loop_count == 0:
            return [
                "Blog(2024): Qdrant does not support hybrid retrieval.",
                "Forum(2025): Qdrant hybrid retrieval is in beta."
            ]
        else:
            return ["Official_Docs(2026): Qdrant supports hybrid retrieval in v1.10+."]

    return []

# ==========================================
# 3. Nodes
# ==========================================
# We use a global to track loops just for the simulation
LOOP_COUNT = 0 

def retrieve_node(state: AgentState):
    global LOOP_COUNT
    new_evidence = retrieve_evidence(state["scenario"], LOOP_COUNT)
    LOOP_COUNT += 1
    
    print("  [Data] Evidence Acquired:")
    for e in new_evidence:
        print(f"    - {e}")
        
    return {"evidence": new_evidence}

def assess_evidence_node(state: AgentState):
    """
    Simulates: llm.with_structured_output(EvidenceAssessment).invoke(state["evidence"])
    """
    print("\n  [Assessor] Evaluating evidence against requirements...")
    evidence_str = str(state["evidence"])
    
    # 1. Detect Contradictions
    if "does not support hybrid" in evidence_str and "hybrid retrieval is in beta" in evidence_str and "Official_Docs" not in evidence_str:
        assessment = EvidenceAssessment(
            sufficient=False, contradictions=["Conflicting claims about hybrid retrieval support."],
            missing_data=["Need an authoritative source (Official Docs) to break the tie."], action="retrieve"
        )
    # 2. Detect Missing Evidence
    elif "hybrid retrieval" not in evidence_str:
        assessment = EvidenceAssessment(
            sufficient=False, contradictions=[],
            missing_data=["Missing data on hybrid retrieval capability."], action="retrieve"
        )
    # 3. Clear to Reason
    else:
        assessment = EvidenceAssessment(sufficient=True, contradictions=[], missing_data=[], action="reason")
        
    if assessment.action == "retrieve":
        print(f"    -> INSUFFICIENT. Missing: {assessment.missing_data} | Contradictions: {assessment.contradictions}")
    else:
        print("    -> SUFFICIENT. Proceeding to Reasoning.")
        
    return {
        "evidence_sufficient": assessment.sufficient, 
        "contradictions_found": bool(assessment.contradictions)
    }

def reason_node(state: AgentState):
    """Generates the final conclusion."""
    print("  [Reasoner] Synthesizing evidence into conclusion...")
    return {"conclusion": "Qdrant satisfies the requirements for metadata filtering and hybrid retrieval."}

def verify_node(state: AgentState):
    """Final deterministic check."""
    print("  [Verifier] Checking conclusion against raw evidence...")
    # Simulation: We assume the Reasoner did its job correctly if it made it this far
    print("    VERIFIED: Conclusion supported by Authoritative Evidence.")
    return {"verified": True}

# ==========================================
# 4. Router
# ==========================================
def route_assessment(state: AgentState) -> Literal["retrieve", "reason"]:
    if state["evidence_sufficient"]:
        return "reason"
    return "retrieve"

# ==========================================
# 5. Build Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("retrieve", retrieve_node)
builder.add_node("assess_evidence", assess_evidence_node)
builder.add_node("reason", reason_node)
builder.add_node("verify", verify_node)

builder.add_edge(START, "retrieve")
builder.add_edge("retrieve", "assess_evidence")
builder.add_conditional_edges("assess_evidence", route_assessment)
builder.add_edge("reason", "verify")
builder.add_edge("verify", END)

graph = builder.compile()

# ==========================================
# 6. Execution Scenarios
# ==========================================
def run_scenario(scenario_name: str):
    global LOOP_COUNT
    LOOP_COUNT = 0
    print(f"\n\n{'='*50}\n=== SCENARIO: {scenario_name.upper()} ===\n{'='*50}")
    graph.invoke({
        "scenario": scenario_name, 
        "question": "Does Qdrant satisfy our retrieval requirements?",
        "requirements": ["metadata filtering", "hybrid retrieval"],
        "evidence": [], "evidence_sufficient": False, "contradictions_found": False,
        "conclusion": None, "verified": False
    })

run_scenario("Sufficient Evidence")
run_scenario("Insufficient Evidence")
run_scenario("Contradictory Evidence")