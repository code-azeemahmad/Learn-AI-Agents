import operator
from typing import Annotated, Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel


# ==========================================
# 1. State & Output Schemas
# ==========================================
class AgentState(TypedDict):
    question: str
    evidence: Annotated[list[str], operator.add]
    next_tool: Optional[str]
    verdict: Optional[str]

class ReasonerDecision(BaseModel):
    needs_more_evidence: bool
    next_tool: Optional[Literal["get_cpu_metrics", "get_db_metrics", "get_slow_queries"]]
    verdict: Optional[str]

# ==========================================
# 2. Simulated Tools
# ==========================================
def get_cpu_metrics():
    print("  [Tool Execution] get_cpu_metrics()")
    return "CPU Load: 45% (Normal)"

def get_db_metrics(fail_mode=False):
    print("  [Tool Execution] get_db_metrics()")
    if fail_mode:
        return "DB Error: Timeout connecting to replica."
    return "DB P95 Latency: 900ms (High)"

def get_slow_queries(empty_mode=False):
    print("  [Tool Execution] get_slow_queries()")
    if empty_mode:
        # FIX: Changed "Slow Queries:" to "Slow Query Check:" for consistent matching
        return "Slow Query Check: None detected in last 5 minutes."
    return "Slow Query Found: 'SELECT * FROM huge_table' (Duration: 780ms)"

# ==========================================
# 3. Graph Nodes
# ==========================================
def reason_node(state: AgentState):
    """
    Simulates the LLM interpreting the evidence and deciding the next move.
    """
    print("\n[Reasoner] Analyzing current evidence...")
    evidence_str = str(state["evidence"])
    
    # Simulating LLM Logic
    if not state["evidence"]:
        decision = ReasonerDecision(needs_more_evidence=True, next_tool="get_cpu_metrics", verdict=None)
        
    elif "CPU Load: 45%" in evidence_str and "DB P95" not in evidence_str and "DB Error" not in evidence_str:
        decision = ReasonerDecision(needs_more_evidence=True, next_tool="get_db_metrics", verdict=None)
        
    # FIX: This check now works correctly because both tool outputs contain "Slow Query"
    elif "DB P95 Latency: 900ms" in evidence_str and "Slow Query" not in evidence_str:
        decision = ReasonerDecision(needs_more_evidence=True, next_tool="get_slow_queries", verdict=None)
        
    elif "DB Error: Timeout" in evidence_str:
        decision = ReasonerDecision(needs_more_evidence=False, next_tool=None, verdict="Critical DB Connection Failure. Cannot query further.")
        
    elif "Slow Query Found" in evidence_str:
        decision = ReasonerDecision(needs_more_evidence=False, next_tool=None, verdict="Likely database query bottleneck. Found slow SELECT statement.")
        
    # FIX: Updated to match the new tool output
    elif "Slow Query Check: None" in evidence_str:
        decision = ReasonerDecision(needs_more_evidence=False, next_tool=None, verdict="DB Latency is high, but no specific slow queries detected. Check DB connection pool.")
        
    print(f"  -> Decision: Next Tool = {decision.next_tool} | Verdict = {decision.verdict}")
    return {"next_tool": decision.next_tool, "verdict": decision.verdict}

def tool_executor_node(state: AgentState):
    """Executes the specific tool requested by the Reasoner."""
    tool = state["next_tool"]
    
    # We use a global variable here just to simulate the different scenarios for the lesson
    global SCENARIO
    
    if tool == "get_cpu_metrics":
        result = get_cpu_metrics()
    elif tool == "get_db_metrics":
        result = get_db_metrics(fail_mode=(SCENARIO == "DB Timeout"))
    elif tool == "get_slow_queries":
        result = get_slow_queries(empty_mode=(SCENARIO == "Conflicting Data"))
        
    return {"evidence": [result]}

# ==========================================
# 4. Router
# ==========================================
def route_after_reasoning(state: AgentState) -> Literal["tool_executor", "__end__"]:
    """Routes to the tool node if more evidence is needed, otherwise ends."""
    if state["next_tool"]:
        return "tool_executor"
    return "__end__"

# ==========================================
# 5. Build Graph
# ==========================================
builder = StateGraph(AgentState)
builder.add_node("reason", reason_node)
builder.add_node("tool_executor", tool_executor_node)

builder.add_edge(START, "reason")
builder.add_conditional_edges("reason", route_after_reasoning)
builder.add_edge("tool_executor", "reason")

graph = builder.compile()

# ==========================================
# 6. Execution Scenarios
# ==========================================
def run_scenario(scenario_name: str):
    global SCENARIO
    SCENARIO = scenario_name
    print(f"\n\n{'='*50}\n=== SCENARIO: {scenario_name.upper()} ===\n{'='*50}")
    
    # Optional: Use a recursion_limit just in case! 
    # LangGraph defaults to 25 loops before throwing a recursion error.
    final_state = graph.invoke(
        {"question": "Why is our API experiencing high latency?", "evidence": [], "next_tool": None, "verdict": None},
        {"recursion_limit": 10} 
    )
    print(f"\n FINAL VERDICT: {final_state['verdict']}")

run_scenario("Standard Investigation")
run_scenario("DB Timeout")
run_scenario("Conflicting Data")