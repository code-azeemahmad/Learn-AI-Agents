from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

# ==========================================
# 1. LangGraph Execution Engine
# ==========================================

class State(TypedDict):
    count: int

def increment(state: State):
    # Safely handle missing keys for a fresh thread
    current_count = state.get("count", 0) 
    return {"count": current_count + 1}

builder = StateGraph(State)
builder.add_node("increment", increment)
builder.add_edge(START, "increment")
builder.add_edge("increment", END)

checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)

# ==========================================
# 2. Application Database (Simulated)
# ==========================================

# A mock PostgreSQL table associating application IDs with LangGraph threads
db_conversations = {
    "conv_001": {"owner_id": 42, "thread_id": "thread-a"},
    "conv_002": {"owner_id": 99, "thread_id": "thread-b"}
}

# ==========================================
# 3. Application Gateway (Simulated FastAPI endpoint)
# ==========================================

def run_chat(user_id: int, conversation_id: str):
    print(f"\n--- Request: User {user_id} attempting to access {conversation_id} ---")
    
    # 1. Database Lookup
    conversation = db_conversations.get(conversation_id)
    if not conversation:
        raise PermissionError(f"Conversation {conversation_id} not found.")
        
    # 2. SECURITY GATE: Authorization check
    if conversation["owner_id"] != user_id:
        raise PermissionError(f"Access Denied! User {user_id} does not own {conversation_id}.")
        
    print("  [Auth] Identity verified. Access granted.")
    
    # 3. Resolve LangGraph Thread
    thread_id = conversation["thread_id"]
    config = {"configurable": {"thread_id": thread_id}}
    
    # 4. Fetch the existing state (Checkpointer)
    current_state = graph.get_state(config)
    
    # If the thread has existing state, use it. Otherwise, start fresh.
    input_state = current_state.values if current_state.values else {"count": 0}
    
    # 5. Invoke Graph with the previous state as input
    result = graph.invoke(input_state, config)
    print(f"  [Graph] Execution Result: {result}")
    return result

# ==========================================
# 4. Execution Tests
# ==========================================

try:
    # Test 1: User 42 accesses their own chat
    run_chat(user_id=42, conversation_id="conv_001")
    
    # Test 2: User 42 accesses their chat again (Checks persistence)
    run_chat(user_id=42, conversation_id="conv_001")
    
    # Test 3: User 99 accesses their own chat (Checks thread isolation)
    run_chat(user_id=99, conversation_id="conv_002")
    
    # Test 4: Malicious attempt! User 99 tries to access User 42's chat
    run_chat(user_id=99, conversation_id="conv_001")
    
except PermissionError as e:
    print(f"  [Security Blocked] {e}")