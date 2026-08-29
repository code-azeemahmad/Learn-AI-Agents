from langchain_core.messages import AIMessage, HumanMessage
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph


# ==========================================
# 1. State Schema
# ==========================================
# We inherit from MessagesState which automatically handles the `operator.add` 
# reducer for the `messages` list under the hood!
class AgentState(MessagesState):
    current_task: str

# ==========================================
# 2. Setup LLM & Node
# ==========================================
# (You can swap this with any LangChain-compatible model)
llm = ChatOllama(model="gemma4:26b", temperature=0)

def chat_node(state: AgentState):
    print("\n  [Node: Chat] Reading previous messages...")
    
    # 1. Pass the entire short-term conversation history to the LLM
    response = llm.invoke(state["messages"])
    
    # 2. Return the new message. The MessagesState reducer will automatically append it.
    return {"messages": [response.content[:100]]}

# ==========================================
# 3. Build & Compile Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("chat", chat_node)
builder.add_edge(START, "chat")
builder.add_edge("chat", END)

# Attach Checkpointer for Thread-Scoped Memory
checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)

# ==========================================
# 4. Execution Tests
# ==========================================

print("=== CONVERSATION 1: Thread 'thread-123' ===")
config_1 = {"configurable": {"thread_id": "thread-123"}}

# Turn 1
print("\nUser: My name is Azeem.")
graph.invoke(
    {
        "messages": [HumanMessage(content="My name is Azeem.")],
        "current_task": "greeting"
    }, 
    config_1
)

# Turn 2
print("\nUser: I am learning AI engineering.")
graph.invoke(
    {"messages": [HumanMessage(content="I am learning AI engineering.")]}, 
    config_1
)

# Turn 3
print("\nUser: What am I learning?")
result_1 = graph.invoke(
    {"messages": [HumanMessage(content="What am I learning?")]}, 
    config_1
)
print(f"Agent: {result_1['messages'][-1].content}")


print("\n\n=== CONVERSATION 2: Thread 'thread-456' ===")
config_2 = {"configurable": {"thread_id": "thread-456"}}

# Turn 1 (New Thread)
print("\nUser: What is my name?")
result_2 = graph.invoke(
    {
        "messages": [HumanMessage(content="What is my name?")],
        "current_task": "query"
    }, 
    config_2
)
print(f"Agent: {result_2['messages'][-1].content}")

# ==========================================
# 5. Inspect the Thread State
# ==========================================
print("\n=== Inspecting Thread 'thread-123' State ===")
saved_state = graph.get_state(config_1)

print(f"Current Task: {saved_state.values['current_task']}")
print("Messages in Memory:")
for msg in saved_state.values["messages"]:
    speaker = "User" if isinstance(msg, HumanMessage) else "Agent"
    print(f"  [{speaker}]: {msg.content}")