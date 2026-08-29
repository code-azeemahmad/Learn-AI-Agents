import operator
from typing import Annotated

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict


# ==========================================
# 1. State Schema
# ==========================================
# Notice the strict separation of concerns
class State(TypedDict):
    # 1. Conversational Context (For the LLM)
    messages: Annotated[list[AnyMessage], operator.add]
    
    # 2. Execution State (For the Router/Graph)
    current_step: int
    
    # 3. Domain/Tool State (For passing data between nodes)
    tool_result: str | None

# ==========================================
# 2. Nodes
# ==========================================
def retrieve_node(state: State):
    """Simulates a tool that fetches data without talking to the LLM."""
    print("  [Node: Retrieve] Fetching documents from Qdrant...")
    
    # We mutate the Domain State and the Execution State.
    # We DO NOT touch the messages history yet.
    return {
        "tool_result": "Relevant Qdrant documents found: [Doc A, Doc B]",
        "current_step": state["current_step"] + 1,
    }

def answer_node(state: State):
    """Simulates an LLM synthesizing an answer from the tool context."""
    print("  [Node: Answer] Formulating response based on tool context...")
    
    # The "LLM" reads the Domain State to generate the Answer
    context = state["tool_result"]
    generated_answer = f"Based on my search, here is the info: {context}"
    
    # We mutate the Conversational Context and Execution State.
    return {
        "messages": [AIMessage(content=generated_answer)],
        "current_step": state["current_step"] + 1,
    }

# ==========================================
# 3. Build & Compile Graph
# ==========================================
builder = StateGraph(State)

builder.add_node("retrieve", retrieve_node)
builder.add_node("answer", answer_node)

builder.add_edge(START, "retrieve")
builder.add_edge("retrieve", "answer")
builder.add_edge("answer", END)

graph = builder.compile()

# ==========================================
# 4. Execution Test
# ==========================================
print("=== Simulating Execution Flow ===")
initial_state = {
    "messages": [HumanMessage(content="What info do we have on Qdrant?")],
    "current_step": 0,
    "tool_result": None
}

final_state = graph.invoke(initial_state)

# ==========================================
# 5. Inspection of State Boundaries
# ==========================================
print("\n=== Inspecting the Final State Boundaries ===")

print("\n1. Conversational Context (What the user and LLM said):")
for msg in final_state["messages"]:
    msg_type = "User" if isinstance(msg, HumanMessage) else "Agent"
    print(f"  [{msg_type}]: {msg.content}")

print("\n2. Execution State (Where the graph finished):")
print(f"  Cursor is now at step: {final_state['current_step']}")

print("\n3. Domain/Tool State (The raw backend data payload):")
print(f"  Payload: {final_state['tool_result']}")