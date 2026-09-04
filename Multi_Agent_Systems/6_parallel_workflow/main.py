import operator
import time
from typing import Annotated, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send


# ==========================================
# 1. State Schema & Reducer
# ==========================================
def merge_results(existing: list, new: list) -> list:
    """Reducer: Combines the parallel worker outputs safely."""
    if not existing: existing = []
    if not new: new = []
    return existing + new

class AgentState(TypedDict):
    scenario: str
    document_content: str
    
    # The array of items we will fan-out over
    chunks: list[str]
    
    # The merged results from the fan-in
    extracted_entities: Annotated[list[str], merge_results]

# State for the individual worker nodes
class WorkerState(TypedDict):
    chunk_text: str

# ==========================================
# 2. Map-Reduce Nodes
# ==========================================
def chunker_node(state: AgentState):
    """The MAP step: Breaks the large task into smaller arrays."""
    print(f"\n{'='*60}\n[Scenario]: {state['scenario']}")
    print(f"  [Chunker] Received large document. Splitting into chunks...")
    
    # Simulating document splitting
    text = state["document_content"]
    chunks = text.split("||")
    
    print(f"  [Chunker] Created {len(chunks)} chunks. Preparing to fan-out...")
    return {"chunks": chunks}


def worker_node(state: WorkerState):
    """The WORKER step: Processes a SINGLE chunk independently."""
    chunk = state["chunk_text"]
    print(f"    [Worker] Booting in parallel... Processing chunk: '{chunk[:15]}...'")
    
    # Simulate LLM Entity Extraction
    time.sleep(0.5) 
    
    extracted = []
    if "Acme" in chunk: extracted.append("Acme Corp")
    if "Globex" in chunk: extracted.append("Globex Inc")
    if "Initech" in chunk: extracted.append("Initech")
    
    print(f"    [Worker] Extraction complete. Found: {extracted}")
    # Return as a list so the Reducer can merge it
    return {"extracted_entities": extracted}


def aggregator_node(state: AgentState):
    """The REDUCE step: Analyzes the merged results."""
    entities = state.get("extracted_entities", [])
    print(f"\n  [Aggregator] All parallel workers finished! Fan-in complete.")
    print(f"  [Aggregator] Merged Entities: {entities}")
    
    # Deduplicate the merged list
    unique_entities = list(set(entities))
    print(f"  [Aggregator] Final Deduplicated List: {unique_entities}")
    return {}

# ==========================================
# 3. Dynamic Routing Edge (The Magic)
# ==========================================
def continue_to_workers(state: AgentState):
    """
    This conditional edge reads the array of chunks, and returns an array of `Send` objects.
    LangGraph will dynamically spawn one `worker_node` for EVERY `Send` object in the array!
    """
    sends = []
    for chunk in state["chunks"]:
        # Send(Destination_Node, State_Payload_For_That_Node)
        sends.append(Send("worker_node", {"chunk_text": chunk}))
        
    return sends

# ==========================================
# 4. Build Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("chunker_node", chunker_node)
builder.add_node("worker_node", worker_node)
builder.add_node("aggregator_node", aggregator_node)

builder.add_edge(START, "chunker_node")

# DYNAMIC FAN-OUT!
# We don't explicitly link chunker -> worker. We use a conditional edge that returns `Send` objects.
builder.add_conditional_edges(
    "chunker_node", # existing node
    continue_to_workers,    # routing function
    ["worker_node"],    # one of the destinations
)

# FAN-IN!
# All dynamic workers automatically flow into the aggregator when they finish.
builder.add_edge("worker_node", "aggregator_node")

builder.add_edge("aggregator_node", END)

graph = builder.compile()

# ==========================================
# 5. Execution Scenarios
# ==========================================
def run(scenario: str, doc: str):
    graph.invoke({"scenario": scenario, "document_content": doc})

# Scenario 1: A small document (2 chunks)
run("Small Document", "Acme signed the contract.||But Globex refused to sign.")

# Scenario 2: A large document (4 chunks)
run("Large Document", "Acme is great.||Initech is okay.||Globex is bad.||Acme is still great.")