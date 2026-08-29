# ======= LangGraph Checkpointing as Short-Term Memory =======

from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph


# ==========================================
# 1. State Schema
# ==========================================
class AgentState(MessagesState):
    # `messages` is inherited automatically with an operator.add reducer
    turn_count: int  # Execution State (Not sent to the LLM)

# ==========================================
# 2. Setup LLM & Node
# ==========================================
llm = ChatOllama(model="gemma4:26b", temperature=0)

def chat_node(state: AgentState):
    # Read the current execution state
    current_turns = state.get("turn_count", 0)
    
    print(f"  [Node: Chat] Processing turn {current_turns + 1}...")
    
    # 1. Provide only the conversation history to the LLM
    response = llm.invoke(state["messages"])
    
    # 2. Return BOTH the new message and the updated execution state
    return {
        "messages": [response.content[:150]],
        "turn_count": current_turns + 1
    }

# ==========================================
# 3. Build & Compile Graph
# ==========================================
builder = StateGraph(AgentState)
builder.add_node("chat", chat_node)
builder.add_edge(START, "chat")
builder.add_edge("chat", END)

# Attach Checkpointer
checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)

# ==========================================
# 4. Helper Function: Inspect State
# ==========================================
def inspect_thread_state(thread_config: dict, label: str):
    print(f"\n--- Inspecting {label} ---")
    state = graph.get_state(thread_config)
    
    if not state.values:
        print("  State is empty.")
        return

    print(f"  Execution State [turn_count]: {state.values.get('turn_count')}")
    print(f"  Conversation State [messages]:")
    for msg in state.values.get("messages", []):
        speaker = "User" if isinstance(msg, HumanMessage) else "Agent"
        # Print a snippet of the message for readability
        print(f"    [{speaker}]: {msg.content[:150]}...")
    print("-" * 40)

# ==========================================
# 5. Execution Tests
# ==========================================

print("=== CONVERSATION 1: thread 'thread-123' ===")
config_1 = {"configurable": {"thread_id": "thread-123"}}

# Turn 1
print("\nUser: My name is Azeem.")
graph.invoke({"messages": [HumanMessage(content="My name is Azeem.")]}, config_1)

# Turn 2
print("\nUser: I'm building an RAG chatbot AI application.")
graph.invoke({"messages": [HumanMessage(content="I'm building an RAG chatbot AI application.")]}, config_1)

# Turn 3
print("\nUser: What am I building?")
result_1 = graph.invoke({"messages": [HumanMessage(content="What am I building?")]}, config_1)
print(f"Agent: {result_1['messages'][-1].content}")

# Inspect Conversation 1
inspect_thread_state(config_1, "Thread 'thread-123'")


print("\n\n=== CONVERSATION 2: thread 'thread-456' ===")
config_2 = {"configurable": {"thread_id": "thread-456"}}

# Turn 1
print("\nUser: What is my name?")
result_2 = graph.invoke({"messages": [HumanMessage(content="What is my name?")]}, config_2)
print(f"Agent: {result_2['messages'][-1].content}")

# Inspect Conversation 2
inspect_thread_state(config_2, "Thread 'thread-456'")