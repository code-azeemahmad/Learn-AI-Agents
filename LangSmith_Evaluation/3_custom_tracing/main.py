import operator
import os
from pathlib import Path
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph
from langsmith import traceable

# ==========================================
# 1. Environment Configuration
# ==========================================
ENV_PATH = Path(r"F:\ai_agents_langgraph\Learn-AI-Agents\LangSmith_Evaluation\.env")
load_dotenv(dotenv_path=ENV_PATH)

model_name = os.getenv("OLLAMA_MODEL_NAME", "gemma4:26b")
llm = ChatOllama(model=model_name, base_url="http://localhost:11434/")

# ==========================================
# 2. Custom Traced Functions
# ==========================================
# We use @traceable so this pure python function shows up as a dedicated Span
# in the LangSmith trace, making it easy to debug if the DB fails!
@traceable(name="Qdrant_Semantic_Search")
def simulated_qdrant_search(query: str) -> str:
    print(f"  [Qdrant] Searching for: '{query}'")
    # Simulate DB latency/logic
    return "Document: All enterprise refunds must be processed within 30 days."

# ==========================================
# 3. State Schema & Nodes
# ==========================================
class AgentState(TypedDict):
    user_query: str
    retrieved_context: str
    final_answer: str

def retrieval_node(state: AgentState):
    print("  [Node] Entering Retrieval Node...")
    # This call will be nested under retrieval_node in the LangSmith Trace!
    context = simulated_qdrant_search(state["user_query"])
    return {"retrieved_context": context}

def synthesis_node(state: AgentState):
    print("  [Node] Entering Synthesis Node...")
    messages = [
        SystemMessage(content=f"Answer the query using this context: {state['retrieved_context']}"),
        HumanMessage(content=state["user_query"])
    ]
    response = llm.invoke(messages)
    return {"final_answer": response.content}

# ==========================================
# 4. Build Graph
# ==========================================
builder = StateGraph(AgentState)
builder.add_node("retrieval", retrieval_node)
builder.add_node("synthesis", synthesis_node)

builder.add_edge(START, "retrieval")
builder.add_edge("retrieval", "synthesis")
builder.add_edge("synthesis", END)

graph = builder.compile()

# ==========================================
# 5. Execution
# ==========================================
if __name__ == "__main__":
    print(f"\n{'='*60}\n[Executing Custom Traced Workflow]")
    
    # We add metadata to easily find this trace in the LangSmith UI
    tracing_config = {
        "tags": ["rag_pipeline", "custom_tracing"],
        "metadata": {"environment": "learning", "user_id": "student_01"}
    }
    
    initial_state = {"user_query": "How many days do I have to request a refund?", "retrieved_context": "", "final_answer": ""}
    
    result = graph.invoke(initial_state, config=tracing_config)
    
    print("\n  [Final Answer]:")
    print(f"  {result['final_answer']}")
    print("\n  [System] Execution complete. Check the LangSmith UI to see the nested Qdrant_Semantic_Search span!")