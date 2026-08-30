from typing import Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel


# ==========================================
# 1. State & Structured Output Schemas
# ==========================================
class AgentState(TypedDict):
    scenario: str
    requirements: list[str]
    evidence: list[str]
    draft: str
    critique: Optional[dict]
    revision_count: int

# The structured output dictating the exact recovery path
class ReflectionDecision(BaseModel):
    action: Literal["accept", "revise", "retrieve", "replan"]
    issues: list[str]

# ==========================================
# 2. Nodes
# ==========================================
def generate_node(state: AgentState):
    """Generates the initial draft based on the scenario."""
    print(f"\n{'='*50}\n[Scenario]: {state['scenario']}")
    
    if state["scenario"] == "Perfect Draft":
        draft = "Architecture: FastAPI + Qdrant. Security: OAuth2. Deploy: AWS."
    elif state["scenario"] == "Weak Draft":
        draft = "Architecture: FastAPI + Qdrant."
    elif state["scenario"] == "Missing Evidence":
        draft = "Architecture: FastAPI + Qdrant. Qdrant is cheap."
    elif state["scenario"] == "Fundamental Flaw":
        draft = "Architecture: Django + MongoDB."
    elif state["scenario"] == "Infinite Loop":
        draft = "I will never write a good draft."
    else:
        draft = state["draft"]
        
    print(f"  [Generate] Draft: '{draft}'")
    return {"draft": draft}

def critique_node(state: AgentState):
    """Evaluates the draft and chooses the appropriate recovery path."""
    print("  [Critic] Evaluating draft against requirements...")
    draft = state["draft"].lower()
    
    # Simulating LLM Critique Logic
    if state["scenario"] == "Perfect Draft":
        decision = ReflectionDecision(action="accept", issues=[])
        
    elif state["scenario"] == "Weak Draft" and "aws" not in draft:
        decision = ReflectionDecision(
            action="revise", 
            issues=["Draft is missing deployment details."]
        )
        
    elif state["scenario"] == "Missing Evidence" and "pricing" not in str(state["evidence"]):
        decision = ReflectionDecision(
            action="retrieve", 
            issues=["Draft claims Qdrant is 'cheap' but there is no pricing evidence to support this."]
        )
        
    elif state["scenario"] == "Fundamental Flaw":
        decision = ReflectionDecision(
            action="replan", 
            issues=["Draft proposes MongoDB, which violates the relational DB constraint. Discard plan."]
        )
        
    elif state["scenario"] == "Infinite Loop":
        decision = ReflectionDecision(action="revise", issues=["Draft is still terrible."])
        
    else:
        # If it survived the revisions, accept it.
        decision = ReflectionDecision(action="accept", issues=[])
        
    print(f"    -> Status: {decision.action.upper()} | Issues: {decision.issues}")
    return {"critique": decision.model_dump()}

def revise_node(state: AgentState):
    count = state.get("revision_count", 0) + 1
    print(f"  [Revise] (Attempt {count}) Improving draft based on critique...")
    
    if state["scenario"] == "Infinite Loop":
        new_draft = state["draft"] # Never improves
    else:
        new_draft = "Architecture: FastAPI + Qdrant. Security: OAuth2. Deploy: AWS. (Evidence applied if retrieved)."
        
    return {"draft": new_draft, "revision_count": count}

def retrieve_node(state: AgentState):
    print("  [Retriever] Gathering missing evidence identified by Critic...")
    new_evidence = state["evidence"] + ["Pricing: Qdrant self-hosted is free."]
    return {"evidence": new_evidence}

def replan_node(state: AgentState):
    print("  [Planner] Strategy fundamentally flawed. Generating new architecture plan...")
    # Typically would wipe the draft and start over. We end the demo here.
    return {"draft": "New Plan: Restarting from scratch."}

# ==========================================
# 3. Reflection Router
# ==========================================
def reflection_router(state: AgentState) -> Literal["accept", "revise", "retrieve", "replan", "force_end"]:
    critique_action = state["critique"]["action"]
    
    # 1. Bounded Loop Protection
    if state.get("revision_count", 0) >= 2 and critique_action != "accept":
        print("  [Router] Max revisions (2) reached. Forcing termination to prevent infinite loop.")
        return "force_end"
        
    # 2. Dynamic Routing based on Critic's decision
    if critique_action == "accept": return "accept"
    if critique_action == "revise": return "revise"
    if critique_action == "retrieve": return "retrieve"
    if critique_action == "replan": return "replan"

# ==========================================
# 4. Build Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("generate", generate_node)
builder.add_node("critique", critique_node)
builder.add_node("revise", revise_node)
builder.add_node("retrieve", retrieve_node)
builder.add_node("replan", replan_node)

builder.add_edge(START, "generate")
builder.add_edge("generate", "critique")

builder.add_conditional_edges("critique", reflection_router, {
    "accept": END,
    "force_end": END,
    "revise": "revise",
    "retrieve": "retrieve",
    "replan": "replan"
})

builder.add_edge("revise", "critique") # Loop back to evaluate the revision
builder.add_edge("retrieve", "revise") # Incorporate new evidence into a new draft
builder.add_edge("replan", END) # In real life, loops back to generation

graph = builder.compile()

# ==========================================
# 5. Execution Scenarios
# ==========================================
reqs = ["explain architecture", "include security", "include observability", "give deployment strategy"]
initial = {"requirements": reqs, "evidence": [], "draft": "", "critique": None, "revision_count": 0}

print("=== REFLECTION LOOP SIMULATION ===")
graph.invoke({**initial, "scenario": "Perfect Draft"})
graph.invoke({**initial, "scenario": "Weak Draft"})
graph.invoke({**initial, "scenario": "Missing Evidence"})
graph.invoke({**initial, "scenario": "Fundamental Flaw"})
graph.invoke({**initial, "scenario": "Infinite Loop"})