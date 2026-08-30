from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel


# ==========================================
# 1. State Schema
# ==========================================
class AgentState(TypedDict):
    scenario: str
    evidence: list[str]
    claim: str
    verification: bool
    attempts: int

# ==========================================
# 2. Nodes
# ==========================================
def reason_node(state: AgentState):
    """Simulates the LLM making a claim based on the evidence."""
    attempts = state.get("attempts", 0) + 1
    print(f"\n[Reasoner] (Attempt {attempts}) Generating claim...")
    
    # Simulating LLM Logic
    if state["scenario"] == "Supported Claim":
        claim = "Qdrant supports filtering."
    elif state["scenario"] == "Unsupported Claim":
        # First attempt hallucinates. Second attempt gets it right.
        if attempts == 1:
            claim = "Qdrant supports feature X."
        else:
            claim = "Qdrant supports filtering."
    elif state["scenario"] == "Math Error":
        # First attempt makes a math error. Second attempt gets it right.
        if attempts == 1:
            claim = "Total cost: 200 + 80 + 35 = 325"
        else:
            claim = "Total cost: 200 + 80 + 35 = 315"
            
    print(f"  -> Generated Claim: '{claim}'")
    return {"claim": claim, "attempts": attempts}

def verify_node(state: AgentState):
    """
    Simulates the Verification Layer. 
    Mixes semantic verification with deterministic code verification.
    """
    claim = state["claim"]
    evidence = state["evidence"]
    print("  [Verifier] Checking claim...")
    
    # 1. Deterministic Verification (Math)
    if "Total cost:" in claim:
        print("    -> Type: Numerical. Using Deterministic Verifier (Python math).")
        # In a real app, you'd parse the numbers out safely.
        if claim == "Total cost: 200 + 80 + 35 = 315":
            verified = True
        else:
            verified = False
            
    # 2. Semantic Verification (Factual Claims)
    else:
        print("    -> Type: Factual. Using Semantic Verifier against Evidence.")
        # Simulating LLM checking if the claim exists in the evidence array
        verified = any(claim in e for e in evidence)

    if verified:
        print("    VERIFIED: Claim is supported.")
    else:
        print("    REJECTED: Claim is unsupported or incorrect.")
        
    return {"verification": verified}

def retrieve_node(state: AgentState):
    """Simulates gathering more evidence after a rejection."""
    print("  [Retriever] Claim rejected. Gathering more authoritative evidence...")
    # Appending more explicit evidence to force the Reasoner to fix its mistake
    new_evidence = state["evidence"] + ["Fact: 200 + 80 + 35 is strictly equal to 315."]
    return {"evidence": new_evidence}

# ==========================================
# 3. Router
# ==========================================
def route_after_verification(state: AgentState) -> Literal["__end__", "retrieve"]:
    """The Bounded Retry Loop"""
    if state["verification"]:
        return "__end__"
        
    # MAX_VERIFICATION_ATTEMPTS = 2
    if state["attempts"] >= 2:
        print("  [Router] Max verification attempts reached. Aborting to prevent infinite loop.")
        return "__end__"
        
    return "retrieve"

# ==========================================
# 4. Build & Compile Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("reason", reason_node)
builder.add_node("verify", verify_node)
builder.add_node("retrieve", retrieve_node)

builder.add_edge(START, "reason")
builder.add_edge("reason", "verify")
builder.add_conditional_edges("verify", route_after_verification)
builder.add_edge("retrieve", "reason")

graph = builder.compile()

# ==========================================
# 5. Execution Scenarios
# ==========================================
def run_scenario(scenario: str, evidence: list[str]):
    print(f"\n\n{'='*50}\n=== SCENARIO: {scenario.upper()} ===\n{'='*50}")
    graph.invoke({"scenario": scenario, "evidence": evidence, "claim": "", "verification": False, "attempts": 0})

# Test 1: Happy Path
run_scenario("Supported Claim", ["Qdrant supports filtering.", "Qdrant supports hybrid search."])

# Test 2: Hallucinated Feature
run_scenario("Unsupported Claim", ["Qdrant supports filtering.", "Qdrant supports hybrid search."])

# Test 3: LLM Math Failure
run_scenario("Math Error", ["Costs: Server 200, DB 80, Storage 35."])