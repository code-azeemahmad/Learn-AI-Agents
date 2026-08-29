from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph

# ==========================================
# 1. Mock Application Database
# ==========================================
# Represents your PostgreSQL `conversations` table
db_conversations = {
    101: {"user_id": 1, "tenant_id": 10, "thread_id": "thread-a"},
    102: {"user_id": 2, "tenant_id": 10, "thread_id": "thread-b"},
}

# ==========================================
# 2. Authorization Layer
# ==========================================
def authorize_conversation(user_id: int, tenant_id: int, conversation_id: int) -> str:
    """
    Validates ownership before exposing the internal LangGraph thread_id.
    """
    print(f"\n[Auth] Validating access for User {user_id} (Tenant {tenant_id}) -> Conv {conversation_id}")
    
    conversation = db_conversations.get(conversation_id)
    
    if not conversation:
        raise PermissionError("Conversation not found.")
        
    if conversation["tenant_id"] != tenant_id:
        raise PermissionError(f"Tenant mismatch. User belongs to Tenant {tenant_id}, but Conversation belongs to Tenant {conversation['tenant_id']}.")
        
    if conversation["user_id"] != user_id:
        raise PermissionError(f"User mismatch. User {user_id} does not own this conversation.")
        
    print(f"  [Auth] ✅ Access Granted. Resolving to internal thread: {conversation['thread_id']}")
    return conversation["thread_id"]

# ==========================================
# 3. LangGraph Runtime
# ==========================================
class AgentState(MessagesState):
    pass

def dummy_agent(state: AgentState):
    # Simply counts the messages to prove state is persisting per thread
    count = len(state["messages"])
    return {"messages": [AIMessage(content=f"Processed message #{count}")]}

builder = StateGraph(AgentState)
builder.add_node("agent", dummy_agent)
builder.add_edge(START, "agent")
builder.add_edge("agent", END)

# Attach Checkpointer
graph = builder.compile(checkpointer=InMemorySaver())

# ==========================================
# 4. Simulated API Endpoint
# ==========================================
def chat_api_endpoint(user_id: int, tenant_id: int, conversation_id: int, message: str):
    try:
        # 1. Authenticate & Authorize
        trusted_thread_id = authorize_conversation(user_id, tenant_id, conversation_id)
        
        # 2. Configure LangGraph Context
        config = {"configurable": {"thread_id": trusted_thread_id}}
        
        # 3. Invoke Graph
        result = graph.invoke({"messages": [HumanMessage(content=message)]}, config)
        print(f"  [LangGraph] Output: {result['messages'][-1].content}")
        
    except PermissionError as e:
        print(f"  [Auth] ❌ 403 Forbidden: {e}")

# ==========================================
# 5. Execution Tests
# ==========================================
print("=== SECURITY & MAPPING TESTS ===")

# Test 1: Allowed Access (User 1, Tenant 10, Conv 101)
chat_api_endpoint(user_id=1, tenant_id=10, conversation_id=101, message="Hello!")

# Test 2: Same Allowed Access (Proving persistence on thread-a)
chat_api_endpoint(user_id=1, tenant_id=10, conversation_id=101, message="Another message.")

# Test 3: Wrong User (User 2 tries to access User 1's conversation)
chat_api_endpoint(user_id=2, tenant_id=10, conversation_id=101, message="I'm trying to steal data.")

# Test 4: Wrong Tenant (User 3 from Tenant 20 tries to access Tenant 10's conversation)
chat_api_endpoint(user_id=3, tenant_id=20, conversation_id=101, message="Tenant breach attempt.")