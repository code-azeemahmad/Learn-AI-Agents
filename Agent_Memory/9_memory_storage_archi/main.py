# lesson_14_4_09_memory_storage.py
from typing import Any, Literal

MemoryCategory = Literal[
    "checkpointer", 
    "postgresql", 
    "qdrant", 
    "object_storage"
]

def determine_storage_backend(memory_type: str, data: Any) -> MemoryCategory:
    """
    Implements the Decision Framework to route 
    different types of memory to the correct backend.
    """
    # Q1: Is it thread execution state?
    if memory_type == "conversation_messages" or memory_type == "execution_cursor":
        return "checkpointer"
        
    # Q4: Is it a large artifact?
    if memory_type == "uploaded_document" or memory_type == "image":
        return "object_storage"
        
    # Q2: Is it exact structured information?
    if memory_type == "user_preference" or memory_type == "project_decision":
        return "postgresql"
        
    # Q3: Does retrieval depend on semantic similarity?
    if memory_type == "past_discussion" or memory_type == "fuzzy_concept":
        return "qdrant"
        
    # Default fallback
    raise ValueError(f"Unknown memory profile: {memory_type}")

def simulate_storage_routing():
    print("=== Memory Storage Router Simulation ===")
    
    test_cases = [
        {
            "desc": "1. Current conversation messages",
            "type": "conversation_messages",
            "data": ["Hello", "I need help with RAG"]
        },
        {
            "desc": "2. User preference: concise answers",
            "type": "user_preference",
            "data": {"key": "response_style", "value": "concise"}
        },
        {
            "desc": "3. Project decision: use Qdrant",
            "type": "project_decision",
            "data": {"project": "knowledge_copilot", "db": "Qdrant"}
        },
        {
            "desc": "4. Past discussion about retrieval optimization",
            "type": "past_discussion",
            "data": "Last month we talked about using BM25 alongside dense vectors to improve multilingual recall..."
        },
        {
            "desc": "5. Uploaded PDF",
            "type": "uploaded_document",
            "data": "<binary_blob_representing_Q3_report.pdf>"
        }
    ]

    for test in test_cases:
        print(f"\nEvaluating: {test['desc']}")
        backend = determine_storage_backend(test["type"], test["data"])
        
        if backend == "checkpointer":
            print("  ➔ Route to: [LangGraph Checkpointer]")
            print("     (Reason: Short-term, thread-scoped execution state)")
            
        elif backend == "postgresql":
            print("  ➔ Route to: [PostgreSQL]")
            print("     (Reason: Long-term, cross-thread, exact key-value lookup)")
            
        elif backend == "qdrant":
            print("  ➔ Route to: [Qdrant]")
            print("     (Reason: Long-term, cross-thread, semantic/fuzzy recall needed)")
            
        elif backend == "object_storage":
            print("  ➔ Route to: [Object Storage (S3 / GCS)]")
            print("     (Reason: Large binary artifact, expensive to store in DBs)")

if __name__ == "__main__":
    simulate_storage_routing()