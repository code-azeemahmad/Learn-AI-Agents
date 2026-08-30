from typing import Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel


# ==========================================
# 1. State & Output Schemas
# ==========================================
class Constraints(BaseModel):
    self_hosted: bool
    max_monthly_cost: float
    preferred_latency_ms: int

class Candidate(BaseModel):
    name: str
    self_hosted: bool
    monthly_cost: float
    latency_ms: int

class ConstraintEvaluation(BaseModel):
    feasible: bool
    hard_violations: list[str]
    soft_violations: list[str]

class AgentState(TypedDict):
    user_prompt: str
    scenario: str
    constraints: Optional[dict]
    candidates: list[dict]
    evaluations: dict
    recommendation: Optional[str]

# ==========================================
# 2. Nodes
# ==========================================
def extract_constraints_node(state: AgentState):
    """
    Simulates: llm.with_structured_output(Constraints).invoke(state["user_prompt"])
    """
    print(f"\n{'='*50}\n[Scenario]: {state['scenario']}")
    print(f"  [LLM Extractor] Parsing natural language: '{state['user_prompt']}'")
    
    # LLM transforms natural language into strict Pydantic bounds
    extracted = Constraints(self_hosted=True, max_monthly_cost=500.0, preferred_latency_ms=100)
    print(f"    -> Structured Bounds: Self-Hosted={extracted.self_hosted}, Max Cost=${extracted.max_monthly_cost}, Target Latency={extracted.preferred_latency_ms}ms")
    return {"constraints": extracted.model_dump()}

def deterministic_evaluator_node(state: AgentState):
    """
    PURE PYTHON: Enforces hard limits. The LLM has no say here.
    """
    print("  [Python Evaluator] Applying constraints deterministically...")
    constraints = Constraints(**state["constraints"])
    candidates = [Candidate(**c) for c in state["candidates"]]
    
    evaluations = {}
    for cand in candidates:
        hard_violations = []
        soft_violations = []
        
        # 1. Hard Constraints (Must satisfy)
        if constraints.self_hosted and not cand.self_hosted:
            hard_violations.append("Cannot be self-hosted")
        if cand.monthly_cost > constraints.max_monthly_cost:
            hard_violations.append(f"Cost (${cand.monthly_cost}) exceeds budget (${constraints.max_monthly_cost})")
            
        # 2. Soft Constraints (Preferences)
        if cand.latency_ms > constraints.preferred_latency_ms:
            soft_violations.append(f"Latency ({cand.latency_ms}ms) exceeds preferred target ({constraints.preferred_latency_ms}ms)")
            
        is_feasible = len(hard_violations) == 0
        evaluations[cand.name] = ConstraintEvaluation(
            feasible=is_feasible, hard_violations=hard_violations, soft_violations=soft_violations
        )
        
        print(f"    -> Candidate {cand.name}: Feasible={is_feasible} | Hard Violations={hard_violations} | Soft Violations={soft_violations}")
        
    return {"evaluations": {k: v.model_dump() for k, v in evaluations.items()}}

def synthesizer_node(state: AgentState):
    """
    LLM Reasoner: Takes the deterministic findings and writes a human-readable summary.
    """
    print("  [LLM Synthesizer] Writing final recommendation based on feasible candidates...")
    evals = state["evaluations"]
    
    feasible_cands = [name for name, e in evals.items() if e["feasible"]]
    
    if not feasible_cands:
        recom = "No candidates satisfy the mandatory constraints. We need to increase the budget or drop the self-hosting requirement."
    elif len(feasible_cands) == 1:
        name = feasible_cands[0]
        recom = f"{name} is the only viable option. Note: {evals[name]['soft_violations'][0]}" if evals[name]['soft_violations'] else f"{name} satisfies all constraints perfectly."
    else:
        recom = f"Multiple viable options: {feasible_cands}. We should score them based on secondary soft objectives."
        
    print(f"    -> FINAL OUTPUT: {recom}")
    return {"recommendation": recom}

# ==========================================
# 3. Build & Compile Graph
# ==========================================
builder = StateGraph(AgentState)
builder.add_node("extract", extract_constraints_node)
builder.add_node("evaluate", deterministic_evaluator_node)
builder.add_node("synthesize", synthesizer_node)

builder.add_edge(START, "extract")
builder.add_edge("extract", "evaluate")
builder.add_edge("evaluate", "synthesize")
builder.add_edge("synthesize", END)

graph = builder.compile()

# ==========================================
# 4. Execution Scenarios
# ==========================================
prompt = "We need something self-hosted, under $500 per month, and preferably below 100ms."
base_state = {"user_prompt": prompt, "constraints": None, "evaluations": {}, "recommendation": None}

# Test 1: Candidate A (Feasible, but slow)
cands_A = [{"name": "Candidate A", "self_hosted": True, "monthly_cost": 350.0, "latency_ms": 150}]
graph.invoke({**base_state, "scenario": "Candidate A", "candidates": cands_A})

# Test 2: Candidate B (Cheaper & Faster, but violates Hard Constraint)
cands_B = [{"name": "Candidate B", "self_hosted": False, "monthly_cost": 200.0, "latency_ms": 80}]
graph.invoke({**base_state, "scenario": "Candidate B", "candidates": cands_B})

# Test 3: Candidate C (Too Expensive)
cands_C = [{"name": "Candidate C", "self_hosted": True, "monthly_cost": 700.0, "latency_ms": 120}]
graph.invoke({**base_state, "scenario": "Candidate C", "candidates": cands_C})