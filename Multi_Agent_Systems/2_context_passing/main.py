import operator
import time
from typing import Annotated, List, Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph


# ==========================================
# 1. State Schema & Reducer
# ==========================================
def merge_findings(existing: list, new: list) -> list:
    """A reducer to safely combine parallel arrays."""
    if not existing: existing = []
    if not new: new = []
    return existing + new

class AgentState(TypedDict):
    scenario: str
    user_query: str
    
    # Reducer: Ensures parallel nodes don't overwrite each other's data!
    agent_findings: Annotated[list[str], merge_findings]
    
    final_answer: Optional[str]

# ==========================================
# 2. Supervisor / Preparation Node
# ==========================================
def supervisor_prep_node(state: AgentState):
    """The Supervisor analyzes the query and prepares explicit sub-tasks."""
    print(f"\n{'='*60}\n[Scenario]: {state['scenario']}")
    print(f"  [Supervisor] Received Query: '{state['user_query']}'")
    
    # In a real app, an LLM would decide if it needs to fan out or not
    print("  [Supervisor] Fanning out to Research and SQL Agents...")
    return {}

# ==========================================
# 3. Parallel Sub-Agents (Strict Context)
# ==========================================
def research_agent_node(state: AgentState):
    """Sub-agent 1: Research"""
    print("    [Research Agent] Booting... Analyzing docs for 'RAG Latency'")
    
    if state["scenario"] == "Context Dumping":
        print("      -> WARNING: I received 100 irrelevant chat messages. My context window is huge!")
        time.sleep(1)
        finding = "[Research] I found some docs about RAG latency... but also some stuff about HR policies from message #4."
    else:
        print("      -> STRICT CONTEXT: I only received the query. Searching docs...")
        time.sleep(1)
        finding = "[Research] Doc #12: RAG latency spiked due to the new embedding model deployment."
        
    # Notice we return a LIST, so the Reducer can merge it
    return {"agent_findings": [finding]}

def sql_agent_node(state: AgentState):
    """Sub-agent 2: SQL Database"""
    print("    [SQL Agent] Booting... Querying database for metrics")
    
    if state["scenario"] == "Context Dumping":
        print("      -> WARNING: I received the entire chat history! I'm confused about which table to query.")
        time.sleep(1)
        finding = "[SQL] SELECT * FROM hr_policies; (Oops, hallucinated wrong table due to context bloat)"
    else:
        print("      -> STRICT CONTEXT: Querying metrics table...")
        time.sleep(1)
        finding = "[SQL] Metrics DB: API latency increased by 400ms at 02:00 UTC."
        
    return {"agent_findings": [finding]}

# ==========================================
# 4. Context Filter & Synthesis
# ==========================================
def synthesis_node(state: AgentState):
    """The Supervisor takes the combined data from the reducer and generates the final answer."""
    findings = state.get("agent_findings", [])
    
    print("\n  [Supervisor Synthesis] Analyzing parallel findings...")
    for f in findings:
        print(f"    - {f}")
        
    if state["scenario"] == "Context Dumping":
        print("\n  [Supervisor Final Output]: I am confused. The database returned HR policies instead of latency metrics.")
    else:
        print("\n  [Supervisor Final Output]: The latency spike of 400ms at 02:00 UTC was caused by the new embedding model deployment.")
        
    return {"final_answer": "Complete"}

# ==========================================
# 5. Build Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("supervisor_prep", supervisor_prep_node)
builder.add_node("research_agent", research_agent_node)
builder.add_node("sql_agent", sql_agent_node)
builder.add_node("synthesis", synthesis_node)

builder.add_edge(START, "supervisor_prep")

# Fan out in parallel
builder.add_edge("supervisor_prep", "research_agent")
builder.add_edge("supervisor_prep", "sql_agent")

# Fan in to Synthesis
builder.add_edge("research_agent", "synthesis")
builder.add_edge("sql_agent", "synthesis")

builder.add_edge("synthesis", END)
graph = builder.compile()

# ==========================================
# 6. Execution Scenarios
# ==========================================
def run(scenario: str):
    graph.invoke({"scenario": scenario, "user_query": "Why did the RAG service latency increase after yesterday's deployment?"})

run("Strict Context Passing")
run("Context Dumping") 