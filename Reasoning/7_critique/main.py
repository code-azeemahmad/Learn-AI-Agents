from typing import Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel


# ==========================================
# 1. State & Output Schemas
# ==========================================
class AgentState(TypedDict):
    scenario: str
    requirements: list[str]
    evidence: list[str]
    draft: str
    verification_passed: bool
    critique: Optional[dict]
    revision_count: int

# The structured rubric the Critic must follow
class CritiqueRubric(BaseModel):
    passes: bool
    issues: list[str]
    missing_requirements: list[str]

# ==========================================
# 2. Nodes
# ==========================================
def generate_node(state: AgentState):
    """Simulates the initial LLM drafting process."""
    print(f"\n[Scenario]: {state['scenario']}")
    
    # We simulate different first drafts based on the scenario
    if state["scenario"] == "Factually Incorrect":
        draft = "Qdrant does not support filtering, but it is a good database."
    elif state["scenario"] == "Incomplete Draft":
        draft = "Qdrant supports filtering and hybrid retrieval, so it is a good choice."
    elif state["scenario"] == "Perfect Draft":
        draft = "Qdrant supports filtering and hybrid retrieval. It can be self-hosted via Docker, making it highly recommended for our workload."
    elif state["scenario"] == "Forced Infinite Loop":
        # Simulate a draft that never improves
        draft = "I will never write a good draft."
    else:
        # The revision step handles the updated draft
        draft = state["draft"]
        
    print(f"  [Generate] Draft: '{draft}'")
    return {"draft": draft}

def verify_node(state: AgentState):
    """
    VERIFICATION: Is the claim factually supported by evidence?
    (Deterministic Check)
    """
    print("  [Verifier] Checking factual accuracy...")
    draft = state["draft"]
    
    # Simple deterministic check against a known hallucination
    if "does not support filtering" in draft:
        print("    VERIFICATION FAILED: Draft contradicts evidence (Qdrant DOES support filtering).")
        return {"verification_passed": False}
        
    print("    VERIFICATION PASSED: No factual hallucinations detected.")
    return {"verification_passed": True}

def critique_node(state: AgentState):
    """
    CRITIQUE: Is the draft high quality? Does it meet all requirements?
    (Semantic Check)
    """
    print("  [Critic] Evaluating draft against requirements...")
    draft = state["draft"].lower()
    reqs = state["requirements"]
    
    missing = []
    issues = []
    
    # Simulating an LLM analyzing the text against the requirements array
    if "self-hosting" not in draft and "self-hosted" not in draft:
        missing.append("Discuss self-hosting")
        issues.append("The draft fails to mention operational/deployment capabilities.")
        
    if "recommended" not in draft and "good choice" not in draft:
        missing.append("Give a recommendation")
        issues.append("The draft lacks a final conclusion or recommendation.")

    # The Forced Infinite Loop scenario simulate a broken LLM that never passes critique
    if state["scenario"] == "Forced Infinite Loop":
         missing = ["Literally everything"]
         issues = ["This draft is terrible."]

    if missing:
        critique = CritiqueRubric(passes=False, issues=issues, missing_requirements=missing)
        print(f"    CRITIQUE FAILED: Missing {missing}")
    else:
        critique = CritiqueRubric(passes=True, issues=[], missing_requirements=[])
        print("    CRITIQUE PASSED: All requirements met.")
        
    return {"critique": critique.model_dump()}

def revise_node(state: AgentState):
    """Revises the draft based on the critique and verification failures."""
    count = state.get("revision_count", 0) + 1
    print(f"  [Revise] (Revision {count}) Improving draft based on feedback...")
    
    if not state["verification_passed"]:
        print("    -> Fixing factual errors...")
        new_draft = "Qdrant DOES support filtering and hybrid retrieval."
    else:
        print("    -> Addressing missing requirements...")
        # Simulate a successful revision addressing the Critic's feedback
        new_draft = "Qdrant supports filtering and hybrid retrieval. It can be self-hosted via Docker, making it highly recommended for our workload."
        
    # If it's the infinite loop test, we intentionally don't improve the draft
    if state["scenario"] == "Forced Infinite Loop":
        new_draft = state["draft"]
        
    return {"draft": new_draft, "revision_count": count}

# ==========================================
# 3. Router
# ==========================================
def reflection_router(state: AgentState) -> Literal["revise", "__end__"]:
    """The central nervous system of the reflection loop."""
    
    # 1. Did it fail Verification? Revise.
    if not state["verification_passed"]:
        return "revise"
        
    # 2. Did it fail Critique? Revise.
    critique = state.get("critique", {})
    if not critique.get("passes", True):
        # PROTECT AGAINST INFINITE LOOPS
        if state.get("revision_count", 0) >= 2:
            print("  [Router] Max revisions reached! Forcing graph to end to save budget.")
            return "__end__"
        return "revise"
        
    # 3. Everything passed!
    return "__end__"

# ==========================================
# 4. Build Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("generate", generate_node)
builder.add_node("verify", verify_node)
builder.add_node("critique", critique_node)
builder.add_node("revise", revise_node)

builder.add_edge(START, "generate")
builder.add_edge("generate", "verify")

# We only run Critique if Verification passes. (Don't waste tokens critiquing a lie).
def route_verify(state: AgentState):
    if state["verification_passed"]: return "critique"
    return "revise"

builder.add_conditional_edges("verify", route_verify)
builder.add_conditional_edges("critique", reflection_router)
builder.add_edge("revise", "verify") # Loop back to the start of the gauntlet

graph = builder.compile()

# ==========================================
# 5. Execution Scenarios
# ==========================================
reqs = ["Explain filtering", "Explain hybrid retrieval", "Discuss self-hosting", "Give a recommendation"]
initial_state = {"requirements": reqs, "evidence": [], "draft": "", "verification_passed": True, "critique": None, "revision_count": 0}

print("=== CRITIQUE & REFLECTION SIMULATION ===")
graph.invoke({**initial_state, "scenario": "Factually Incorrect"})
graph.invoke({**initial_state, "scenario": "Incomplete Draft"})
graph.invoke({**initial_state, "scenario": "Perfect Draft"})
graph.invoke({**initial_state, "scenario": "Forced Infinite Loop"})