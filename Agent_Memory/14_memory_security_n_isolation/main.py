from typing import Literal, Optional

from pydantic import BaseModel

# ==========================================
# 1. Memory Database
# ==========================================
mock_db = [
    {"id": "m1", "tenant_id": "tenant-A", "user_id": "user-1", "scope": "user", "content": "User 1 prefers concise answers."},
    {"id": "m2", "tenant_id": "tenant-A", "user_id": "user-2", "scope": "user", "content": "User 2 prefers detailed answers."},
    {"id": "m3", "tenant_id": "tenant-A", "user_id": None, "scope": "tenant", "content": "Company uses PostgreSQL."},
    {"id": "m4", "tenant_id": "tenant-B", "user_id": "user-3", "scope": "user", "content": "Tenant B Private information."},
]

class LLMMemoryCandidate(BaseModel):
    # This is what the LLM outputs. NEVER trust it blindly.
    proposed_user_id: str
    proposed_tenant_id: str
    proposed_scope: Literal["user", "tenant"]
    content: str

# ==========================================
# 2. Secure Retrieval Layer
# ==========================================
def secure_retrieve_memories(auth_tenant: str, auth_user: str) -> list[dict]:
    """
    Enforces Row-Level Security BEFORE passing data to the LLM.
    """
    print(f"\n[Auth Read] Request from User: {auth_user} | Tenant: {auth_tenant}")
    
    authorized_memories = []
    for mem in mock_db:
        # Hard Tenant Boundary
        if mem["tenant_id"] != auth_tenant:
            continue
            
        # Scope Boundaries within the authorized Tenant
        if mem["scope"] == "tenant":
            authorized_memories.append(mem)
        elif mem["scope"] == "user" and mem["user_id"] == auth_user:
            authorized_memories.append(mem)
            
    return authorized_memories

# ==========================================
# 3. Secure Write Layer
# ==========================================
def secure_write_memory(auth_tenant: str, auth_user: str, is_admin: bool, candidate: LLMMemoryCandidate):
    """
    Enforces Data Integrity and Authorization before writing to the database.
    """
    print(f"\n[Auth Write] Request from User: {auth_user} (Admin: {is_admin}) | Tenant: {auth_tenant}")
    print(f"  [LLM Payload] Proposed Scope: {candidate.proposed_scope} | Proposed User: {candidate.proposed_user_id} | Proposed Tenant: {candidate.proposed_tenant_id}")
    
    # SECURITY 1: Ignore LLM Identity Spoofing
    if candidate.proposed_tenant_id != auth_tenant or candidate.proposed_user_id != auth_user:
        print("  SECURITY WARNING: LLM attempted identity spoofing. Overriding with Auth Context.")
        
    actual_tenant = auth_tenant
    actual_user = auth_user
    
    # SECURITY 2: Role-Based Access Control (RBAC) for Scopes
    if candidate.proposed_scope == "tenant":
        if not is_admin:
            print("  403 Forbidden: Standard users cannot write Tenant-scoped memory.")
            return
        # Admins can write tenant memory, user_id becomes None for organization-wide facts
        actual_user = None 

    print("  Authorized: Writing memory to database.")
    new_mem = {
        "id": f"m{len(mock_db)+1}",
        "tenant_id": actual_tenant,
        "user_id": actual_user,
        "scope": candidate.proposed_scope,
        "content": candidate.content
    }
    mock_db.append(new_mem)

# ==========================================
# 4. Execution Tests
# ==========================================

print("=== MEMORY SECURITY SIMULATION ===")

# --- READ TESTS ---
# Test 1: User 1 in Tenant A gets their data + Tenant data. 
# They DO NOT get User 2's data or Tenant B's data.
results_u1 = secure_retrieve_memories(auth_tenant="tenant-A", auth_user="user-1")
for r in results_u1:
    print(f"  -> Returned: [{r['scope'].upper()}] {r['content']}")

# Test 2: User 3 in Tenant B gets their data. 
# They DO NOT get Tenant A's database standard.
results_u3 = secure_retrieve_memories(auth_tenant="tenant-B", auth_user="user-3")
for r in results_u3:
    print(f"  -> Returned: [{r['scope'].upper()}] {r['content']}")

# --- WRITE TESTS ---
# Test 3: Regular User tries to write a Tenant-wide memory (Should Fail)
evil_candidate_1 = LLMMemoryCandidate(
    proposed_user_id="user-1", proposed_tenant_id="tenant-A", proposed_scope="tenant", 
    content="Company standard is now MongoDB."
)
secure_write_memory(auth_tenant="tenant-A", auth_user="user-1", is_admin=False, candidate=evil_candidate_1)

# Test 4: LLM tries to spoof another user (Should Sandbox)
evil_candidate_2 = LLMMemoryCandidate(
    proposed_user_id="user-2", proposed_tenant_id="tenant-A", proposed_scope="user", 
    content="I hate Python."
)
# We pass User 1's auth context. The system should override the LLM's proposed "user-2".
secure_write_memory(auth_tenant="tenant-A", auth_user="user-1", is_admin=False, candidate=evil_candidate_2)

# Verify the sandbox worked
print("\n--- Final DB State ---")
for mem in mock_db[-1:]:  # Check the last inserted record
    print(f"Inserted Record -> Tenant: {mem['tenant_id']} | User: {mem['user_id']} | Content: {mem['content']}")