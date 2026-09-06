from typing import Literal, Optional, TypedDict

from langchain_core.runnables.config import RunnableConfig
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph


# ==========================================
# 1. State Schema
# ==========================================
class AgentState(TypedDict):
    scenario: str
    tool_calls: int
    final_output: str

# ==========================================
# 2. Nodes
# ==========================================
def llm_node(state: AgentState):
    """
    Simulates a confused LLM that ALWAYS wants to call a tool,
    creating an infinite loop.
    """
    print(f"  [Agent] Thinking... (Step {state.get('tool_calls', 0)})")
    
    if state["scenario"] == "Safe Execution" and state.get("tool_calls", 0) >= 1:
        # It finishes safely after 1 tool call
        return {"final_output": "I am done!"}
        
    # The agent gets stuck in a loop!
    return {"final_output": "I need more data. Calling tool..."}


def tool_node(state: AgentState):
    """Simulates a tool executing and returning data to the agent."""
    current_calls = state.get("tool_calls", 0) + 1
    print(f"  [Tool] Executing database query #{current_calls}...")
    return {"tool_calls": current_calls}

# ==========================================
# 3. Routing
# ==========================================
def router(state: AgentState) -> Literal["tool", "__end__"]:
    if "I am done!" in state.get("final_output", ""):
        return "__end__"
    return "tool"

# ==========================================
# 4. Build Graph
# ==========================================
builder = StateGraph(AgentState)
builder.add_node("llm", llm_node)
builder.add_node("tool", tool_node)

builder.add_edge(START, "llm")
builder.add_conditional_edges("llm", router)
builder.add_edge("tool", "llm") # The dangerous loop!

graph = builder.compile()

# ==========================================
# 5. Execution API
# ==========================================
def run_with_limits(scenario: str, recursion_limit: int):
    print(f"\n{'='*60}\n[Scenario]: {scenario} (Limit: {recursion_limit})")
    
    # THE SECURITY BOUNDARY: We strictly bound the maximum graph transitions!
    config = {"recursion_limit": recursion_limit}
    initial_state = {"scenario": scenario, "tool_calls": 0, "final_output": ""}
    
    try:
        graph.invoke(initial_state, config=config)
        print("  [System Output]: Graph completed successfully.")
    except GraphRecursionError:
        print(f"  [System Output]: GraphRecursionError! The agent exceeded {recursion_limit} steps. Execution terminated to prevent Denial-of-Wallet.")


# 1. Normal execution finishes within the limit
run_with_limits("Safe Execution", recursion_limit=5)

# 2. Infinite Loop intercepted by LangGraph!
run_with_limits("Infinite Loop Bug", recursion_limit=5)