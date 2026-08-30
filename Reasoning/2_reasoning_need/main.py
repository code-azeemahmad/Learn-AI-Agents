from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel


# ==========================================
# 1. State & Output Schemas
# ==========================================
class AgentState(TypedDict):
    scenario: str
    evidence: list[str]
    verdict: str
    confidence: str

# Structured output we expect from the LLM
class ReasoningDecision(BaseModel):
    is_suitable: bool
    confidence: Literal["HIGH", "LOW", "CONFLICT"]
    explanation: str

# ==========================================
# 2. Nodes
# ==========================================
def gather_evidence_node(state: AgentState):
    """Simulates retrieving different sets of evidence based on the scenario."""
    print(f"\n[Scenario]: {state['scenario']}")
    
    if state["scenario"] == "Clear Evidence":
        evidence = [
            "Req: Must be self-hosted.",
            "Req: Must support hybrid search.",
            "Fact: Qdrant can be self-hosted via Docker.",
            "Fact: Qdrant supports hybrid search natively."
        ]
    elif state["scenario"] == "Missing Evidence":
        evidence = [
            "Req: Must be self-hosted.",
            "Req: Must support hybrid search.",
            "Fact: Qdrant can be self-hosted via Docker."
            # Note: Missing fact about hybrid search
        ]
    elif state["scenario"] == "Conflicting Evidence":
        evidence = [
            "Req: Must support hybrid search.",
            "Fact (Blog 2022): Qdrant does not support hybrid search.",
            "Fact (Docs 2024): Qdrant supports hybrid search natively."
        ]
        
    print("  [Data] Evidence gathered:")
    for e in evidence:
        print(f"    - {e}")
        
    return {"evidence": evidence}

def reason_node(state: AgentState):
    """
    Simulates the LLM reasoning over the provided evidence.
    In production, this is where `llm.with_structured_output(ReasoningDecision)` lives.
    """
    evidence = state["evidence"]
    print("  [Reasoning] Analyzing evidence...")
    
    # Simulating LLM Logic
    has_self_host_req = any("Req: Must be self-hosted" in e for e in evidence)
    has_hybrid_req = any("Req: Must support hybrid search" in e for e in evidence)
    
    fact_self_host = any("Fact: Qdrant can be self-hosted" in e for e in evidence)
    fact_hybrid_yes = any("Fact (Docs 2024)" in e or "supports hybrid search natively" in e for e in evidence)
    fact_hybrid_no = any("does not support hybrid search" in e for e in evidence)
    
    # 1. Conflict Detection
    if fact_hybrid_yes and fact_hybrid_no:
        decision = ReasoningDecision(
            is_suitable=False,
            confidence="CONFLICT",
            explanation="Conflicting information found regarding hybrid search. Need authoritative verification."
        )
    # 2. Missing Evidence Detection
    elif (has_self_host_req and not fact_self_host) or (has_hybrid_req and not fact_hybrid_yes):
        decision = ReasoningDecision(
            is_suitable=False,
            confidence="LOW",
            explanation="Insufficient evidence to confirm all requirements. Missing data on hybrid search."
        )
    # 3. Clear Confirmation
    else:
        decision = ReasoningDecision(
            is_suitable=True,
            confidence="HIGH",
            explanation="All requirements (self-hosting, hybrid search) are explicitly supported by the evidence."
        )
        
    return {"verdict": decision.explanation, "confidence": decision.confidence}

def verify_node(state: AgentState):
    """Acts on the reasoning conclusion."""
    confidence = state["confidence"]
    print(f"  [Verification] Confidence Level: {confidence}")
    
    if confidence == "HIGH":
        print(f"  FINAL VERDICT: {state['verdict']}")
    elif confidence == "LOW":
        print(f"  ACTION REQUIRED: {state['verdict']} -> Triggering Tool: Web Search...")
    elif confidence == "CONFLICT":
        print(f"  ACTION REQUIRED: {state['verdict']} -> Triggering Tool: Official Docs Search...")

# ==========================================
# 3. Build & Execute Graph
# ==========================================
builder = StateGraph(AgentState)
builder.add_node("gather_evidence", gather_evidence_node)
builder.add_node("reason", reason_node)
builder.add_node("verify", verify_node)

builder.add_edge(START, "gather_evidence")
builder.add_edge("gather_evidence", "reason")
builder.add_edge("reason", "verify")
builder.add_edge("verify", END)

graph = builder.compile()

print("=== REASONING OVER EVIDENCE SIMULATION ===")
graph.invoke({"scenario": "Clear Evidence", "evidence": [], "verdict": "", "confidence": ""})
graph.invoke({"scenario": "Missing Evidence", "evidence": [], "verdict": "", "confidence": ""})
graph.invoke({"scenario": "Conflicting Evidence", "evidence": [], "verdict": "", "confidence": ""})