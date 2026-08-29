from typing import Literal

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict


# ==========================================
# 1. State Schema
# ==========================================
class AgentState(TypedDict):
    messages: list[str]
    summary: str
    context_budget: int

# ==========================================
# 2. Nodes
# ==========================================
def agent_node(state: AgentState):
    """Simulates the LLM receiving the context and generating a reply."""
    # The actual context passed to the LLM is just the Summary + Recent Messages
    # NOT the entire list!
    recent_messages = state["messages"][-2:] # In reality, maybe last 5-10
    
    print("\n  [Agent Node] Context received by LLM:")
    print(f"    - Summary: '{state['summary']}'")
    print(f"    - Recent Messages ({len(recent_messages)}): {recent_messages}")
    
    # Simulate generating a response
    new_message = f"Agent reply to message {len(state['messages']) + 1}"
    
    # We append to the full history. We DO NOT delete history here.
    return {"messages": state["messages"] + [new_message]}

def compress_node(state: AgentState):
    """Simulates an LLM summarizing the oldest messages."""
    print("\n  [Compress Node] Context limit exceeded! Summarizing old messages...")
    
    # In a real app, you would pass state["summary"] + state["messages"][:-5] to an LLM
    new_summary = f"User is building a RAG app. We have discussed {len(state['messages'])} topics so far."
    
    # We return the new summary. Notice we DO NOT delete the messages from state.
    # The original history remains intact in the Checkpointer for auditing/retrieval.
    return {"summary": new_summary}

# ==========================================
# 3. Router (The Compression Trigger)
# ==========================================
def should_compress(state: AgentState) -> Literal["compress_node", "agent_node"]:
    """Routes to the compressor if the message count exceeds the budget."""
    if len(state["messages"]) > state["context_budget"]:
        return "compress_node"
    return "agent_node"

# ==========================================
# 4. Build & Compile Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("agent_node", agent_node)
builder.add_node("compress_node", compress_node)

# Entry point routes based on current budget
builder.add_conditional_edges(START, should_compress)

# After compression, ALWAYS route back to the agent to answer the user
builder.add_edge("compress_node", "agent_node")

# Agent finishes the turn
builder.add_edge("agent_node", END)

graph = builder.compile()

# ==========================================
# 5. Execution Tests
# ==========================================
def run_simulation():
    print("=== MEMORY COMPRESSION SIMULATION ===")
    
    # Initial State (Pre-filled with 5 messages to simulate an ongoing chat)
    state = {
        "messages": ["Msg 1", "Msg 2", "Msg 3", "Msg 4", "Msg 5"],
        "summary": "No summary yet.",
        "context_budget": 5  # Strict budget: trigger compression if > 5
    }
    
    print("\n--- Turn 1: Budget NOT Exceeded ---")
    # Sending the 5th message (Does not trigger compression)
    state = graph.invoke(state)
    
    print("\n--- Turn 2: Budget EXCEEDED ---")
    # Sending the 6th message (Triggers compression before agent replies)
    state["messages"].append("User Msg 6")
    state = graph.invoke(state)

if __name__ == "__main__":
    run_simulation()