from typing import TypedDict, Optional
from datetime import datetime

# ==========================================
# 1. Long-Term Memory Schema & Store
# ==========================================
class Memory(TypedDict):
    id: str
    user_id: int
    type: str
    key: str
    value: str
    created_at: str

# In a real app, this is PostgreSQL
mock_database: list[Memory] = []

def write_memory(user_id: int, mem_type: str, key: str, value: str):
    """Saves a structured fact about a user that persists across all their threads."""
    new_mem = {
        "id": f"m-{len(mock_database) + 1}",
        "user_id": user_id,
        "type": mem_type,
        "key": key,
        "value": value,
        "created_at": datetime.now().isoformat()
    }
    mock_database.append(new_mem)
    print(f"  [DB Write] Saved Memory for User {user_id}: {key} = '{value}'")

def get_user_memory(user_id: int, key: str) -> Optional[str]:
    """Retrieves a specific memory, ensuring strict user isolation."""
    # We filter by user_id to prevent data leakage between users
    for mem in mock_database:
        if mem["user_id"] == user_id and mem["key"] == key:
            print(f"  [DB Read] Found Memory for User {user_id}: {key} = '{mem['value']}'")
            return mem["value"]
            
    print(f"  [DB Read] No '{key}' memory found for User {user_id}.")
    return None

def delete_user_memory(user_id: int, key: str):
    """Allows users to control/delete their data."""
    global mock_database
    initial_length = len(mock_database)
    mock_database = [mem for mem in mock_database if not (mem["user_id"] == user_id and mem["key"] == key)]
    if len(mock_database) < initial_length:
        print(f"  [DB Delete] Erased '{key}' memory for User {user_id}.")

# ==========================================
# 2. Simulated Workflow (Context Builder)
# ==========================================
def build_prompt_with_memory(user_id: int, current_request: str) -> str:
    """
    Simulates the Context Builder from the lesson. 
    It queries long-term memory BEFORE sending the prompt to the LLM.
    """
    print(f"\n[Context Builder] Processing request for User {user_id}...")
    
    # 1. Fetch relevant long-term memory
    pref_style = get_user_memory(user_id, "response_style")
    pref_db = get_user_memory(user_id, "preferred_database")
    
    # 2. Construct the system instructions dynamically
    system_instructions = "You are a helpful AI."
    if pref_style:
        system_instructions += f"\n- RULE: Ensure your response is {pref_style}."
    if pref_db:
        system_instructions += f"\n- CONTEXT: The user prefers {pref_db}."
        
    # 3. Combine into final prompt
    final_prompt = f"SYSTEM:\n{system_instructions}\n\nUSER:\n{current_request}"
    return final_prompt

# ==========================================
# 3. Execution Tests
# ==========================================

print("=== Thread 1: User 1 sets a preference ===")
# Imagine an agent extracted this from a conversation and called a tool to save it.
write_memory(user_id=1, mem_type="preference", key="response_style", value="concise and bulleted")
write_memory(user_id=1, mem_type="preference", key="preferred_database", value="PostgreSQL")

print("\n=== Thread 2: User 1 starts a NEW conversation ===")
# Weeks later, User 1 asks a question in a completely different thread.
# Notice how the Context Builder fetches the memory to personalize the prompt.
prompt_u1 = build_prompt_with_memory(user_id=1, current_request="Write a report on our database schema.")
print(f"\nFINAL PROMPT TO LLM:\n{prompt_u1}")

print("\n=== Thread 3: User 2 (Isolation Test) ===")
# User 2 logs in and asks a similar question. They should NOT get User 1's preferences.
prompt_u2 = build_prompt_with_memory(user_id=2, current_request="Write a report on our database schema.")
print(f"\nFINAL PROMPT TO LLM:\n{prompt_u2}")

print("\n=== Thread 4: User 1 Deletes Memory ===")
# User 1 decides they no longer want bulleted lists.
delete_user_memory(user_id=1, key="response_style")
prompt_u1_updated = build_prompt_with_memory(user_id=1, current_request="Write a report on our database schema.")
print(f"\nFINAL PROMPT TO LLM:\n{prompt_u1_updated}")