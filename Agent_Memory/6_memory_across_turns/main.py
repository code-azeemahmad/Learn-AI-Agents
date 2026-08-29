# lesson_14_4_06_context.py

def recent_messages(messages: list[str], limit: int = 5) -> list[str]:
    """Truncates the message list to the most recent N messages."""
    return messages[-limit:]

def simulate_context_builder():
    # ==========================================
    # 1. Simulate Persisted Checkpoint State
    # ==========================================
    print("=== 1. The Persisted Storage (Checkpoint) ===")
    
    # Imagine these are 20 full messages from a long-running thread
    stored_messages = [f"[Message {i}]" for i in range(1, 21)]
    stored_messages[0] = "[Message 1] We decided to use Qdrant for this project."
    stored_messages[-1] = "[Message 20] What database did we choose?"
    
    # Assume a background process generates this periodically
    stored_summary = "User is building an AI application using FastAPI and Qdrant."
    
    print(f"Total Stored Messages: {len(stored_messages)}")
    print(f"Oldest Message: {stored_messages[0]}")
    print(f"Newest Message: {stored_messages[-1]}")
    
    # ==========================================
    # 2. Context Builder (Windowing Only)
    # ==========================================
    print("\n=== 2. Strategy: Recent Window (Context Loss) ===")
    
    # We only take the last 5 messages
    context_recent_only = recent_messages(stored_messages, limit=5)
    
    print("Context sent to LLM:")
    for msg in context_recent_only:
        print(f"  {msg}")
        
    print("\n Note: The LLM has lost the context from [Message 1]. It doesn't know the database!")

    # ==========================================
    # 3. Context Builder (Hybrid)
    # ==========================================
    print("\n=== 3. Strategy: Hybrid (Summary + Recent) ===")
    
    # We combine the rolling summary with the recent interaction
    hybrid_context = {
        "System Summary": stored_summary,
        "Recent Conversation": recent_messages(stored_messages, limit=5)
    }
    
    print("Context sent to LLM:")
    print(f"  [Summary]: {hybrid_context['System Summary']}")
    for msg in hybrid_context["Recent Conversation"]:
        print(f"  {msg}")
        
    print("\n Note: The LLM can now answer [Message 20] using the injected Summary, while keeping token counts low.")

if __name__ == "__main__":
    simulate_context_builder()