from typing import Literal, Optional

from typing_extensions import TypedDict


# ==========================================
# 1. Advanced Memory Schema
# ==========================================
class Memory(TypedDict):
    id: str
    key: str
    value: str
    scope: Literal["user", "project", "tenant"]
    source: str
    confidence: float
    status: Literal["active", "superseded"]

# Initial Database State
mock_memory_store: list[Memory] = [
    {
        "id": "m1", "key": "response_style", "value": "concise", 
        "scope": "user", "source": "explicit_user_statement", 
        "confidence": 1.0, "status": "active"
    },
    {
        "id": "m2", "key": "project_database", "value": "Qdrant", 
        "scope": "project", "source": "project_configuration", 
        "confidence": 1.0, "status": "active"
    }
]

# ==========================================
# 2. Write Policy: Conflict Resolution
# ==========================================
def process_memory_candidate(new_memory: dict):
    print(f"\n[Write Pipeline] Processing New Candidate: {new_memory['key']} = {new_memory['value']}")
    
    # 1. Find Existing Active Memories with the same key and scope
    existing_memories = [
        m for m in mock_memory_store 
        if m["key"] == new_memory["key"] and m["scope"] == new_memory["scope"] and m["status"] == "active"
    ]
    
    if not existing_memories:
        print("  [Conflict Check] No active conflicts found. Creating new active memory.")
        mock_memory_store.append(new_memory)
        return
        
    # 2. Conflict Detected! Apply Resolution Policy
    for old_mem in existing_memories:
        print(f"  [Conflict Check] Conflict detected! Existing active value is '{old_mem['value']}'")
        
        # Policy A: Explicit User Corrections override existing preferences
        if new_memory["source"] == "explicit_user_correction":
            print(f"  [Resolution] Explicit user correction detected. Superseding '{old_mem['value']}'.")
            old_mem["status"] = "superseded"
            mock_memory_store.append(new_memory)
            
        # Policy B: Authoritative Config updates override existing configurations
        elif new_memory["source"] == "project_configuration":
            print(f"  [Resolution] Authoritative config update detected. Superseding '{old_mem['value']}'.")
            old_mem["status"] = "superseded"
            mock_memory_store.append(new_memory)
            
        # Policy C: Weak Agent Inferences DO NOT override explicit statements
        elif new_memory["source"] == "agent_inference" and old_mem["source"] == "explicit_user_statement":
            print("  [Resolution] Rejected. Agent inference cannot override an explicit user statement.")

# ==========================================
# 3. Read Policy: Current vs Historical Retrieval
# ==========================================
def retrieve_memory(key: str, scope: str, query_type: Literal["current", "historical"]) -> list[Memory]:
    """Retrieves memories based on the intent of the query."""
    print(f"\n[Read Pipeline] Querying '{key}' (Scope: {scope}) | Intent: {query_type.upper()}")
    
    if query_type == "current":
        # Only return active memories
        results = [m for m in mock_memory_store if m["key"] == key and m["scope"] == scope and m["status"] == "active"]
    else:
        # Return historical context (superseded memories)
        results = [m for m in mock_memory_store if m["key"] == key and m["scope"] == scope]
        
    for res in results:
        print(f"  -> Found: {res['value']} (Status: {res['status']})")
    return results

# ==========================================
# 4. Execution Tests
# ==========================================
print("=== CONFLICT RESOLUTION SIMULATION ===")

# Test 1: User corrects their preference
process_memory_candidate({
    "id": "m3", "key": "response_style", "value": "detailed", 
    "scope": "user", "source": "explicit_user_correction", 
    "confidence": 1.0, "status": "active"
})

# Test 2: Project infrastructure changes
process_memory_candidate({
    "id": "m4", "key": "project_database", "value": "Pinecone", 
    "scope": "project", "source": "project_configuration", 
    "confidence": 1.0, "status": "active"
})

# Test 3: Agent makes a weak inference (Should be rejected)
process_memory_candidate({
    "id": "m5", "key": "response_style", "value": "bullet_points", 
    "scope": "user", "source": "agent_inference", 
    "confidence": 0.4, "status": "active"
})

print("\n=== RETRIEVAL SIMULATION ===")

# Query A: "What is the current project database?"
retrieve_memory("project_database", "project", "current")

# Query B: "What database did we use before?"
retrieve_memory("project_database", "project", "historical")

# Query C: "What is the user's preference?"
retrieve_memory("response_style", "user", "current")