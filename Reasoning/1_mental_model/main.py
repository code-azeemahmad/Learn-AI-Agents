from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel


# ==========================================
# 1. State & Structured Output Schemas
# ==========================================
class AgentState(TypedDict):
    question: str
    evidence: list[str]
    reasoning_result: str
    decision: dict
    verified: bool

class Decision(BaseModel):
    suitable: bool
    reason: str

# ==========================================
# 2. Nodes
# ==========================================
def gather_evidence_node(state: AgentState):
    """ACTING: Finding the data."""
    print(f"\n[Acting] Gathering evidence for: '{state['question']}'")
    
    # Simulating a RAG retrieval or Tool Call
    simulated_evidence = [
        "The system must be self-hosted.",
        "The system requires metadata filtering.",
        "The system requires hybrid retrieval.",
        "Qdrant supports metadata filtering.",
        "Qdrant supports hybrid retrieval.",
        "Qdrant can be deployed locally via Docker."
    ]
    
    return {"evidence": simulated_evidence}

def reasoning_node(state: AgentState):
    """REASONING: Interpreting the data."""
    print("\n[Reasoning] Analyzing evidence against requirements...")
    
    evidence = state["evidence"]
    
    # Simulating LLM analysis to produce a structured decision
    # In a real app, you would pass `evidence` to `llm.with_structured_output(Decision)`
    has_filtering = any("metadata filtering" in e and "Qdrant" in e for e in evidence)
    has_hybrid = any("hybrid retrieval" in e and "Qdrant" in e for e in evidence)
    can_self_host = any("locally" in e and "Qdrant" in e for e in evidence)
    
    if has_filtering and has_hybrid and can_self_host:
        decision = Decision(
            suitable=True, 
            reason="Qdrant meets all requirements: self-hosted via Docker, supports metadata filtering, and hybrid retrieval."
        )
    else:
        decision = Decision(
            suitable=False, 
            reason="Evidence does not support all requirements."
        )
        
    print(f"  -> Conclusion: {decision.reason}")
    return {"decision": decision.model_dump(), "reasoning_result": decision.reason}

def verification_node(state: AgentState):
    """VERIFICATION: Checking the reasoning."""
    print("\n[Verification] Verifying the reasoning conclusion...")
    
    conclusion = state["reasoning_result"]
    evidence = state["evidence"]
    
    # Simulating an LLM Critic checking if the conclusion is actually supported by the text
    # In a real app, this is an LLM prompt: "Does this evidence justify this conclusion?"
    if "Qdrant meets all requirements" in conclusion and len(evidence) >= 6:
        print("  -> Verdict: VALIDATED. The evidence strongly supports the conclusion.")
        return {"verified": True}
    else:
        print("  -> Verdict: REJECTED. The evidence does not support the conclusion.")
        return {"verified": False}

# ==========================================
# 3. Build & Compile Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("gather_evidence", gather_evidence_node)
builder.add_node("reason", reasoning_node)
builder.add_node("verify", verification_node)

builder.add_edge(START, "gather_evidence")
builder.add_edge("gather_evidence", "reason")
builder.add_edge("reason", "verify")
builder.add_edge("verify", END)

graph = builder.compile()

# ==========================================
# 4. Execution
# ==========================================
print("=== AGENT REASONING PIPELINE ===")
final_state = graph.invoke({
    "question": "Should we use Qdrant for a self-hosted RAG system?",
    "evidence": [],
    "reasoning_result": "",
    "decision": {},
    "verified": False
})