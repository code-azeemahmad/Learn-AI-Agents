from typing import Optional, TypedDict

from langgraph.graph import END, START, StateGraph


# ==========================================
# 1. Research SUBGRAPH Definition
# ==========================================
# This state ONLY exists inside the Subgraph. The Main Graph can't see it!
class ResearchState(TypedDict):
    query: str
    internal_keywords: Optional[list[str]]
    raw_docs: Optional[list[str]]
    final_artifact: Optional[str]

def rewrite_query_node(state: ResearchState):
    print("    [Subgraph: Research] Step 1: Rewriting query into keywords...")
    return {"internal_keywords": ["finance", "policy", "q3"]}

def fetch_docs_node(state: ResearchState):
    print(f"    [Subgraph: Research] Step 2: Fetching DB using keywords: {state['internal_keywords']}...")
    return {"raw_docs": ["Doc1: Policy X", "Doc2: Policy Y"]}

def format_artifact_node(state: ResearchState):
    print("    [Subgraph: Research] Step 3: Formatting raw docs into clean artifact...")
    return {"final_artifact": "Research Report: Finance policies were updated in Q3."}

# Build the Subgraph
research_builder = StateGraph(ResearchState)
research_builder.add_node("rewrite", rewrite_query_node)
research_builder.add_node("fetch", fetch_docs_node)
research_builder.add_node("format", format_artifact_node)

research_builder.add_edge(START, "rewrite")
research_builder.add_edge("rewrite", "fetch")
research_builder.add_edge("fetch", "format")
research_builder.add_edge("format", END)

# COMPILE THE SUBGRAPH
research_subgraph = research_builder.compile()

# ==========================================
# 2. Main Graph Definition
# ==========================================
# This is the Global State
class MainState(TypedDict):
    user_request: str
    research_report: Optional[str]
    final_answer: Optional[str]

def prepare_node(state: MainState):
    print(f"\n{'='*60}\n[Main Graph] Received Request: '{state['user_request']}'")
    print("[Main Graph] Delegating to Research Subgraph...")
    return {}

def call_subgraph_node(state: MainState):
    """
    We invoke the compiled subgraph here.
    We pass it ONLY the data it needs to start.
    We extract ONLY the final artifact when it finishes.
    """
    # 1. Map MainState -> SubgraphState
    subgraph_input = {"query": state["user_request"]}
    
    # 2. Execute the Subgraph
    subgraph_output = research_subgraph.invoke(subgraph_input)
    
    # 3. Map SubgraphState -> MainState
    return {"research_report": subgraph_output["final_artifact"]}

def synthesis_node(state: MainState):
    print("[Main Graph] Synthesizing final answer using Research Report...")
    print(f"  -> Report Data: {state['research_report']}")
    return {"final_answer": "Complete"}

# Build the Main Graph
main_builder = StateGraph(MainState)
main_builder.add_node("prepare", prepare_node)
main_builder.add_node("research", call_subgraph_node) # Calling our custom wrapper node
main_builder.add_node("synthesis", synthesis_node)

main_builder.add_edge(START, "prepare")
main_builder.add_edge("prepare", "research")
main_builder.add_edge("research", "synthesis")
main_builder.add_edge("synthesis", END)

main_graph = main_builder.compile()

# ==========================================
# 3. Execution
# ==========================================
main_graph.invoke({"user_request": "What is the new finance policy?"})