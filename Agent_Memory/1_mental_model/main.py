from typing import TypedDict


# ==========================================
# 1. State Schema
# ==========================================
class AgentState(TypedDict):
    messages: list[str]       # Conversation History
    current_task: str         # Execution Context
    current_step: int         # Execution Cursor
    tool_results: list[str]   # Working Memory

def simulate_workflow():
    # ==========================================
    # Step 1: Initial Request
    # ==========================================
    print("=== Step 1: Initial State ===")
    state: AgentState = {
        "messages": ["User: Find information about Qdrant"],
        "current_task": "Research Qdrant",
        "current_step": 1,
        "tool_results": [],
    }
    print(f"Messages: {state['messages']}")
    print(f"Task: {state['current_task']} | Cursor: {state['current_step']}")
    print(f"Tool Results: {state['tool_results']}\n")

    # ==========================================
    # Step 2: Tool Execution Node
    # ==========================================
    print("=== Step 2: Tool Execution (State Mutation) ===")
    # The agent uses a tool, and we mutate the working memory
    state["tool_results"].append("Qdrant supports vector search and filtering.")
    state["current_step"] = 2
    print(f"Tool Results: {state['tool_results']}")
    print(f"Next Cursor: {state['current_step']}\n")

    # ==========================================
    # Step 3: LLM Response Node
    # ==========================================
    print("=== Step 3: Conversation History Update ===")
    # The agent reads `tool_results` to answer, then updates `messages`
    state["messages"].append("Agent: Qdrant supports vector search and filtering.")
    state["messages"].append("User: Does it support hybrid search?")
    state["current_step"] = 3
    
    print("Updated Messages:")
    for msg in state['messages']:
        print(f"  - {msg}")
        
    print(f"\nFinal Tool Context: {state['tool_results']}")

if __name__ == "__main__":
    simulate_workflow()