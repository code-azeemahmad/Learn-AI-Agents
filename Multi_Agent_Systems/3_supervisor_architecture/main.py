from typing import Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph


# ==========================================
# 1. State Schema
# ==========================================
# Notice how the state explicitly tracks the results of sub-agents
class AgentState(TypedDict):
    scenario: str
    user_request: str
    
    research_result: Optional[str]
    sql_result: Optional[str]
    
    iteration_count: int
    next_agent: Literal["research", "sql", "finish", "error"]

# ==========================================
# 2. Simulated LLM Supervisor
# ==========================================
def supervisor_node(state: AgentState):
    """
    The Supervisor reads the current state and decides what to do next.
    In a real app, this is an LLM outputting structured JSON.
    """
    iterations = state.get("iteration_count", 0) + 1
    print(f"\n  [Supervisor] Iteration {iterations} | Analyzing State...")
    
    # Safety Boundary: Max Iterations
    if iterations >= 5:
        print("    -> Max iterations reached! Forcing termination.")
        return {"next_agent": "finish", "iteration_count": iterations}

    # Simulate LLM Reasoning based on the state
    if state["scenario"] == "Simple Query":
        # It already knows the answer! No sub-agents needed.
        print("    -> I can answer this immediately. Routing to Finish.")
        return {"next_agent": "finish", "iteration_count": iterations}
        
    elif state["scenario"] == "Complex Query":
        # It needs both pieces of information
        if not state.get("research_result"):
            print("    -> I need research data first. Routing to Research Agent.")
            return {"next_agent": "research", "iteration_count": iterations}
            
        elif not state.get("sql_result"):
            print("    -> I have research data, now I need DB metrics. Routing to SQL Agent.")
            return {"next_agent": "sql", "iteration_count": iterations}
            
        else:
            print("    -> I have all the data I need! Routing to Finish.")
            return {"next_agent": "finish", "iteration_count": iterations}
            
    elif state["scenario"] == "LLM Hallucination":
        # The LLM goes crazy and outputs an illegal string
        print("    -> Routing to: 'hack_the_mainframe'")
        # We simulate the Pydantic validation failing and returning 'error'
        return {"next_agent": "error", "iteration_count": iterations}

# ==========================================
# 3. Sub-Agent Nodes (The Workers)
# ==========================================
def research_node(state: AgentState):
    print("    [Research Agent] Extracting context... Found 3 documents.")
    return {"research_result": "Docs: Finance policies updated in Q3."}

def sql_node(state: AgentState):
    print("    [SQL Agent] Executing query... Retrieved 50 rows.")
    return {"sql_result": "DB: Total expenses were $1.2M."}

def error_handler_node(state: AgentState):
    """Catches illegal routes chosen by the LLM."""
    print("    [System] Invalid route selected by LLM. Returning control to Supervisor to retry.")
    return {}

# ==========================================
# 4. Routing Edge Logic
# ==========================================
def route_supervisor_decision(state: AgentState) -> Literal["research", "sql", "error_handler", "__end__"]:
    """Maps the Supervisor's decision to actual graph nodes."""
    decision = state["next_agent"]
    
    if decision == "research": return "research"
    if decision == "sql": return "sql"
    if decision == "error": return "error_handler"
    
    return "__end__" # finish

# ==========================================
# 5. Build Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("supervisor", supervisor_node)
builder.add_node("research", research_node)
builder.add_node("sql", sql_node)
builder.add_node("error_handler", error_handler_node)

builder.add_edge(START, "supervisor")

# The Supervisor controls the flow
builder.add_conditional_edges("supervisor", route_supervisor_decision)

# The Workers always return control BACK to the Supervisor
builder.add_edge("research", "supervisor")
builder.add_edge("sql", "supervisor")
builder.add_edge("error_handler", "supervisor")

graph = builder.compile()

# ==========================================
# 6. Execution Scenarios
# ==========================================
def run(scenario: str):
    print(f"\n{'='*60}\n=== SCENARIO: {scenario.upper()} ===\n{'='*60}")
    
    initial_state = {
        "scenario": scenario, "user_request": "Dummy request",
        "research_result": None, "sql_result": None,
        "iteration_count": 0, "next_agent": "finish"
    }
    
    final_state = graph.invoke(initial_state)
    print(f"\n  FINAL STATE -> Research: {bool(final_state.get('research_result'))} | SQL: {bool(final_state.get('sql_result'))} | Iterations: {final_state['iteration_count']}")

run("Simple Query")
run("Complex Query")
run("LLM Hallucination")