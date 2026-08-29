from typing import Literal, Optional
from typing_extensions import TypedDict

# ==========================================
# 1. Scoped Memory Schema
# ==========================================
class Memory(TypedDict):
    id: str
    scope: Literal["conversation", "user", "tenant"]
    tenant_id: str
    user_id: Optional[str]
    conversation_id: Optional[str]
    key: str
    value: str

# ==========================================
# 2. Mock Database (Simulating PostgreSQL/Vector Store)
# ==========================================
mock_memory_store: list[Memory] = [
    # Tenant A Memory (Shared by User A and User B)
    {"id": "m1", "scope": "tenant", "tenant_id": "org-alpha", "user_id": None, "conversation_id": None, "key": "db_standard", "value": "PostgreSQL"},
    
    # User A Memory
    {"id": "m2", "scope": "user", "tenant_id": "org-alpha", "user_id": "user-a", "conversation_id": None, "key": "style", "value": "Concise"},
    
    # User A Conversation Memory
    {"id": "m3", "scope": "conversation", "tenant_id": "org-alpha", "user_id": "user-a", "conversation_id": "conv-101", "key": "current_topic", "value": "Qdrant filtering"},
    
    # User B Memory
    {"id": "m4", "scope": "user", "tenant_id": "org-alpha", "user_id": "user-b", "conversation_id": None, "key": "style", "value": "Detailed"},
    
    # Tenant B Memory (Isolated from Tenant A)
    {"id": "m5", "scope": "tenant", "tenant_id": "org-beta", "user_id": None, "conversation_id": None, "key": "db_standard", "value": "MongoDB"},
]

# ==========================================
# 3. Scope-Enforced Retrieval Functions
# ==========================================
def get_tenant_memories(tenant_id: str) -> list[Memory]:
    """Retrieves memories shared across the entire organization."""
    return [m for m in mock_memory_store if m["scope"] == "tenant" and m["tenant_id"] == tenant_id]

def get_user_memories(tenant_id: str, user_id: str) -> list[Memory]:
    """Retrieves personal memories. Validates tenant as an extra security boundary."""
    return [m for m in mock_memory_store if m["scope"] == "user" and m["user_id"] == user_id and m["tenant_id"] == tenant_id]

def get_conversation_memories(tenant_id: str, user_id: str, conversation_id: str) -> list[Memory]:
    """Retrieves thread-specific memories. Validates both user and tenant ownership."""
    return [m for m in mock_memory_store if m["scope"] == "conversation" and m["conversation_id"] == conversation_id and m["user_id"] == user_id and m["tenant_id"] == tenant_id]

# ==========================================
# 4. Context Builder Simulation
# ==========================================
def build_context(tenant_id: str, user_id: str, conversation_id: str):
    print(f"\n[Context Builder] Building context for {user_id} (Tenant: {tenant_id}, Conv: {conversation_id})")
    
    # Fetch all authorized scopes
    t_mems = get_tenant_memories(tenant_id)
    u_mems = get_user_memories(tenant_id, user_id)
    c_mems = get_conversation_memories(tenant_id, user_id, conversation_id)
    
    # Display the constructed context
    print("  --- Assembled Context ---")
    
    if t_mems:
        print("  Organization Memory:")
        for m in t_mems:
            print(f"      - {m['key']}: {m['value']}")
            
    if u_mems:
        print("  Personal Memory:")
        for m in u_mems:
            print(f"      - {m['key']}: {m['value']}")
            
    if c_mems:
        print("  Active Conversation Context:")
        for m in c_mems:
            print(f"      - {m['key']}: {m['value']}")
            
    if not any([t_mems, u_mems, c_mems]):
        print("  No memory found or access denied.")
    print("  -------------------------")

# ==========================================
# 5. Execution Tests
# ==========================================
print("=== MEMORY ISOLATION TESTS ===")

# Test 1: User A in Tenant A (Should get Tenant A, User A, and Conv 101)
build_context(tenant_id="org-alpha", user_id="user-a", conversation_id="conv-101")

# Test 2: User B in Tenant A (Should get Tenant A, User B. Should NOT see User A's style or Conv 101)
build_context(tenant_id="org-alpha", user_id="user-b", conversation_id="conv-202")

# Test 3: User C in Tenant B (Should get Tenant B. Should NOT see Tenant A's database standard)
build_context(tenant_id="org-beta", user_id="user-c", conversation_id="conv-303")