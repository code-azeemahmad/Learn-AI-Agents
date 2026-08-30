from enum import Enum
from typing import Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel


# ==========================================
# 1. State & Output Schemas
# ==========================================
class FailureType(str, Enum):
    MISSING_EVIDENCE = "missing_evidence"
    CONFLICT = "conflict"
    CONSTRAINT = "constraint"
    INVALID_RESULT = "invalid_result"
    NONE = "none"

class ValidationResult(BaseModel):
    valid: bool
    failure_type: FailureType
    message: str

class AgentState(TypedDict):
    scenario: str
    evidence: list[str]
    candidate: Optional[dict]
    constraint: Optional[str]
    attempts: int
    validation: Optional[dict]

# ==========================================
# 2. Nodes
# ==========================================
def gather_evidence_node(state: AgentState):
    """Mocks initial data gathering."""
    print(f"\n{'='*50}\n[Scenario]: {state['scenario']}")
    
    if state["scenario"] == "Missing Evidence":
        evidence = []
    elif state["scenario"] == "Conflict":
        evidence = ["Feature X is supported.", "Feature X is not supported."]
    else:
        evidence = state.get("evidence", ["Fact: Feature X is supported."])
        
    return {"evidence": evidence}

def reason_node(state: AgentState):
    """Simulates the LLM forming a conclusion."""
    attempts = state.get("attempts", 0) + 1
    print(f"  [Reasoner] (Attempt {attempts}) Generating conclusion...")
    return {"attempts": attempts}

def validate_node(state: AgentState):
    """
    The brain of the resilience system. Categorizes the exact nature of the failure.
    """
    print("  [Validator] Checking conclusion for failures...")
    
    # Simulating LLM / Code Validation Logic
    if not state["evidence"]:
        val = ValidationResult(valid=False, failure_type=FailureType.MISSING_EVIDENCE, message="Cannot proceed without evidence.")
        
    elif any("not supported" in e for e in state["evidence"]) and any("is supported" in e for e in state["evidence"]):
        val = ValidationResult(valid=False, failure_type=FailureType.CONFLICT, message="Contradictory evidence detected in sources.")
        
    elif state.get("candidate") and state.get("constraint"):
        if state["candidate"]["deployment"] != state["constraint"]:
            val = ValidationResult(valid=False, failure_type=FailureType.CONSTRAINT, message=f"Candidate deployment ({state['candidate']['deployment']}) violates hard constraint ({state['constraint']}).")
        else:
            val = ValidationResult(valid=True, failure_type=FailureType.NONE, message="Valid and Supported.")
            
    else:
        val = ValidationResult(valid=True, failure_type=FailureType.NONE, message="Valid and Supported.")
        
    if not val.valid:
        print(f"    FAILURE DETECTED: [{val.failure_type.value.upper()}] {val.message}")
    else:
        print("    VALIDATION PASSED.")
        
    return {"validation": val.model_dump()}

# Specialized Recovery Nodes
def retrieve_node(state: AgentState):
    print("    [Recovery -> Retriever] Executing search to find missing evidence...")
    return {"evidence": ["Fact: Feature X is supported."]}

def verify_source_node(state: AgentState):
    print("    [Recovery -> Source Verifier] Querying official documentation to break conflict...")
    return {"evidence": ["Official Docs(2026): Feature X is supported."]}

def replan_node(state: AgentState):
    print("    [Recovery -> Planner] Hard constraint violated. Generating new architecture plan...")
    return {"candidate": {"deployment": "self_hosted"}}

# ==========================================
# 3. Router
# ==========================================
def failure_router(state: AgentState) -> Literal["retrieve", "verify_source", "replan", "__end__"]:
    val = state["validation"]
    
    # 1. Bounded Recovery Check
    if state["attempts"] >= 2 and not val["valid"]:
        print("  [Router] Max attempts reached. Graceful Abstention: 'I cannot confidently answer this.'")
        return "__end__"
        
    # 2. Success
    if val["valid"]:
        return "__end__"
        
    # 3. Specialized Recovery Routing
    f_type = val["failure_type"]
    if f_type == FailureType.MISSING_EVIDENCE: return "retrieve"
    if f_type == FailureType.CONFLICT: return "verify_source"
    if f_type == FailureType.CONSTRAINT: return "replan"
    
    return "__end__"

# ==========================================
# 4. Build Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("gather_evidence", gather_evidence_node)
builder.add_node("reason", reason_node)
builder.add_node("validate", validate_node)
builder.add_node("retrieve", retrieve_node)
builder.add_node("verify_source", verify_source_node)
builder.add_node("replan", replan_node)

builder.add_edge(START, "gather_evidence")
builder.add_edge("gather_evidence", "reason")
builder.add_edge("reason", "validate")

# Route based on the failure type
builder.add_conditional_edges("validate", failure_router)

# All recovery nodes loop back to reason
builder.add_edge("retrieve", "reason")
builder.add_edge("verify_source", "reason")
builder.add_edge("replan", "reason")

graph = builder.compile()

# ==========================================
# 5. Execution Scenarios
# ==========================================
print("=== AGENT FAILURE RECOVERY SIMULATION ===")

# Test 1: Missing Evidence
graph.invoke({"scenario": "Missing Evidence", "evidence": [], "attempts": 0, "validation": None})

# Test 2: Conflict
graph.invoke({"scenario": "Conflict", "evidence": [], "attempts": 0, "validation": None})

# Test 3: Constraint Violation
graph.invoke({
    "scenario": "Constraint Violation", 
    "candidate": {"deployment": "managed"}, 
    "constraint": "self_hosted", 
    "attempts": 0, "validation": None
})

# Test 4: Max Attempts Reached (Graceful Abstention)
# We feed it a permanent conflict to simulate a scenario where recovery fails
graph.invoke({"scenario": "Permanent Conflict", "evidence": ["Yes", "No"], "attempts": 1, "validation": None})