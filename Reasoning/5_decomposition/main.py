import operator
from typing import Annotated, Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel


# ==========================================
# 1. Structured Output Schemas
# ==========================================
class Subproblem(BaseModel):
    id: int
    question: str

class SubproblemResult(BaseModel):
    id: int
    question: str
    finding: str
    confidence: float
    status: Literal["resolved", "insufficient_evidence", "conflict"]

class Synthesis(BaseModel):
    decision: str
    supporting_findings: list[str]
    unresolved_questions: list[str]

# ==========================================
# 2. State Schema
# ==========================================
class AgentState(TypedDict):
    scenario: str
    main_task: str
    subproblems: list[Subproblem]
    sub_results: Annotated[list[SubproblemResult], operator.add]
    final_synthesis: Optional[dict]

# ==========================================
# 3. Nodes
# ==========================================
def decompose_node(state: AgentState):
    """
    Simulates: llm.with_structured_output(list[Subproblem]).invoke(state["main_task"])
    """
    print(f"\n{'='*50}\n[Scenario]: {state['scenario']}\n[Task]: {state['main_task']}")
    print("  [Decomposer] Breaking down the main task...")
    
    # We break the big question down into 3 targeted questions
    subproblems = [
        Subproblem(id=1, question="What are the core requirements?"),
        Subproblem(id=2, question="Does Qdrant satisfy the requirements?"),
        Subproblem(id=3, question="Is Qdrant operationally viable for our team?")
    ]
    
    for sp in subproblems:
        print(f"    - Subproblem {sp.id}: {sp.question}")
        
    return {"subproblems": subproblems}

def evaluate_candidates_node(state: AgentState):
    """
    Simulates localized reasoning for each subproblem.
    In a real app, this would be a parallel map (Send each Subproblem to its own LLM node).
    """
    print("  [Evaluator] Processing subproblems locally...")
    results = []
    
    for sp in state["subproblems"]:
        if sp.id == 1:
            res = SubproblemResult(
                id=1, question=sp.question, finding="Requires hybrid search and self-hosting.", 
                confidence=1.0, status="resolved"
            )
        
        elif sp.id == 2:
            if state["scenario"] == "Conflict":
                res = SubproblemResult(
                    id=2, question=sp.question, finding="Docs say yes, but a recent engineering blog says no.", 
                    confidence=0.5, status="conflict"
                )
            else:
                res = SubproblemResult(
                    id=2, question=sp.question, finding="Qdrant supports hybrid search natively.", 
                    confidence=0.9, status="resolved"
                )
                
        elif sp.id == 3:
            if state["scenario"] == "Missing Data":
                res = SubproblemResult(
                    id=3, question=sp.question, finding="Pricing and memory overhead are unknown.", 
                    confidence=0.2, status="insufficient_evidence"
                )
            else:
                res = SubproblemResult(
                    id=3, question=sp.question, finding="Docker deployment fits existing infrastructure.", 
                    confidence=0.9, status="resolved"
                )
                
        results.append(res)
        
    for r in results:
        print(f"    -> [Result {r.id}] Status: {r.status.upper()} | Finding: {r.finding}")
        
    return {"sub_results": results}

def synthesize_node(state: AgentState):
    """
    Simulates: llm.with_structured_output(Synthesis).invoke(state["sub_results"])
    """
    print("  [Synthesizer] Reviewing all sub-results to form a final conclusion...")
    
    results = state["sub_results"]
    
    # Simulating LLM Synthesis Logic
    conflicts = [r for r in results if r.status == "conflict"]
    missing = [r for r in results if r.status == "insufficient_evidence"]
    resolved = [r for r in results if r.status == "resolved"]
    
    if conflicts:
        synth = Synthesis(
            decision="Cannot recommend Qdrant at this time due to conflicting evidence.",
            supporting_findings=[r.finding for r in resolved],
            unresolved_questions=[f"CONFLICT: {r.finding}" for r in conflicts]
        )
    elif missing:
        synth = Synthesis(
            decision="Qdrant looks promising, but operational viability requires further investigation.",
            supporting_findings=[r.finding for r in resolved],
            unresolved_questions=[f"MISSING: {r.finding}" for r in missing]
        )
    else:
        synth = Synthesis(
            decision="Qdrant is highly recommended.",
            supporting_findings=[r.finding for r in resolved],
            unresolved_questions=[]
        )
        
    print(f"    -> FINAL DECISION: {synth.decision}")
    if synth.unresolved_questions:
        print(f"    -> WARNINGS: {synth.unresolved_questions}")
        
    return {"final_synthesis": synth.model_dump()}

# ==========================================
# 4. Build & Compile Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("decompose", decompose_node)
builder.add_node("evaluate", evaluate_candidates_node)
builder.add_node("synthesize", synthesize_node)

builder.add_edge(START, "decompose")
builder.add_edge("decompose", "evaluate")
builder.add_edge("evaluate", "synthesize")
builder.add_edge("synthesize", END)

graph = builder.compile()

# ==========================================
# 5. Execution
# ==========================================
initial_state = {
    "main_task": "Should we use Qdrant for our RAG application?",
    "subproblems": [], "sub_results": [], "final_synthesis": None
}

graph.invoke({**initial_state, "scenario": "Perfect Match"})
graph.invoke({**initial_state, "scenario": "Missing Data"})
graph.invoke({**initial_state, "scenario": "Conflict"})