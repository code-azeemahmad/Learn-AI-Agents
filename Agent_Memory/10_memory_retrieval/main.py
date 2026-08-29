import math
from datetime import datetime, timedelta

# ==========================================
# 1. Mock Storage (PostgreSQL for KV, Qdrant for Semantic)
# ==========================================

# Structured Data (Simulating PostgreSQL)
structured_memories = [
    {"user_id": 1, "scope": "user", "type": "preference", "key": "response_style", "value": "concise"},
    {"user_id": 1, "scope": "user", "type": "technology", "key": "backend", "value": "FastAPI"},
    {"user_id": 2, "scope": "user", "type": "preference", "key": "response_style", "value": "detailed"},
]

# Semantic Data (Simulating Qdrant)
now = datetime.now()
semantic_memories = [
    {
        "id": "m1", "user_id": 1, "text": "User is building an internal RAG application.", 
        "created_at": now - timedelta(days=30), "importance": 0.8
    },
    {
        "id": "m2", "user_id": 1, "text": "User is currently evaluating vector databases.", 
        "created_at": now - timedelta(days=2), "importance": 0.9
    },
    {
        "id": "m3", "user_id": 1, "text": "User had pizza for lunch.", 
        "created_at": now, "importance": 0.1
    },
    {
        "id": "m4", "user_id": 2, "text": "User is building a mobile application.", 
        "created_at": now, "importance": 0.9
    },
]

# ==========================================
# 2. Retrieval & Ranking Logic
# ==========================================

def get_structured_memories(user_id: int) -> list[dict]:
    """Retrieves exact key-value facts for a specific user."""
    return [m for m in structured_memories if m["user_id"] == user_id]

def simulate_semantic_search(query: str, user_id: int) -> list[dict]:
    """
    Simulates a vector search with metadata filtering.
    Only returns memories belonging to the specified user.
    """
    # 1. Scope Filter (CRITICAL SECURITY STEP)
    user_memories = [m for m in semantic_memories if m["user_id"] == user_id]
    
    # 2. Simulate Semantic Scoring (Fuzzy string matching for the demo)
    results = []
    query_lower = query.lower()
    for mem in user_memories:
        # Fake semantic score based on keyword overlap
        score = sum(1 for word in query_lower.split() if word in mem["text"].lower()) / 10.0
        results.append({
            "memory": mem,
            "semantic_score": min(score, 1.0)
        })
    return results

def calculate_recency_score(created_at: datetime) -> float:
    """Decays score based on how old the memory is."""
    days_old = (datetime.now() - created_at).days
    return max(0.0, 1.0 - (days_old * 0.05)) # Linear decay for demo

def rank_and_select(semantic_results: list[dict], top_k: int = 2) -> list[dict]:
    """Ranks memories using a composite score (Relevance + Recency + Importance)."""
    scored_candidates = []
    
    for result in semantic_results:
        mem = result["memory"]
        semantic = result["semantic_score"]
        recency = calculate_recency_score(mem["created_at"])
        importance = mem["importance"]
        
        # Composite Score Formula
        final_score = (semantic * 0.6) + (recency * 0.2) + (importance * 0.2)
        
        scored_candidates.append({
            "text": mem["text"],
            "score": final_score,
            "metrics": f"[Sem: {semantic:.2f} | Rec: {recency:.2f} | Imp: {importance:.2f}]"
        })
        
    # Sort descending and truncate to top_k budget
    scored_candidates.sort(key=lambda x: x["score"], reverse=True)
    return scored_candidates[:top_k]

# ==========================================
# 3. The Full Context Builder Pipeline
# ==========================================

def build_context(user_id: int, query: str):
    print(f"\n=== Processing Query for User {user_id} ===")
    print(f"Query: '{query}'")
    
    # 1. Fetch Exact Structured Facts
    print("\n  [Retrieving Structured Memory (PostgreSQL)]")
    exact_facts = get_structured_memories(user_id)
    for fact in exact_facts:
        print(f"    - {fact['key']}: {fact['value']}")
        
    # 2. Fetch Semantic Context
    print("\n  [Retrieving Semantic Memory (Qdrant)]")
    semantic_candidates = simulate_semantic_search(query, user_id)
    
    # 3. Rank and Filter to Top K Budget
    print("  [Ranking Candidates (Relevance + Recency + Importance)]")
    final_semantic_memories = rank_and_select(semantic_candidates, top_k=2)
    
    for mem in final_semantic_memories:
        print(f"    - (Score: {mem['score']:.2f}) {mem['metrics']} -> {mem['text']}")

# ==========================================
# 4. Tests
# ==========================================

# Test 1: User 1 asking about their current AI work
build_context(user_id=1, query="What database should I use for my RAG application?")

# Test 2: User 2 (Isolation Test)
build_context(user_id=2, query="What database should I use for my RAG application?")