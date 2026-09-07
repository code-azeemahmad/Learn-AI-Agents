import os
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph

# ==========================================
# 1. Environment Configuration
# ==========================================
ENV_PATH = Path(r"F:\ai_agents_langgraph\Learn-AI-Agents\LangSmith_Evaluation\.env")
load_dotenv(dotenv_path=ENV_PATH)

model_name = os.getenv("OLLAMA_MODEL_NAME", "gemma4:26b")
llm = ChatOllama(model=model_name, base_url="http://localhost:11434/")

# ==========================================
# 2. State Schema & Nodes
# ==========================================
class AgentState(TypedDict):
    question: str
    retrieved_context: str
    answer: str

def retrieve_node(state: AgentState):
    print("  [Node] Simulating retrieval...")
    return {"retrieved_context": "The standard enterprise refund window is 30 days."}

def generate_node(state: AgentState):
    print("  [Node] Generating response using Ollama...")
    messages = [
        SystemMessage(content=f"Answer the user using this context: {state['retrieved_context']}"),
        HumanMessage(content=state["question"])
    ]
    response = llm.invoke(messages)
    return {"answer": response.content}

# ==========================================
# 3. Build Graph
# ==========================================
builder = StateGraph(AgentState)
builder.add_node("retrieve", retrieve_node)
builder.add_node("generate", generate_node)

builder.add_edge(START, "retrieve")
builder.add_edge("retrieve", "generate")
builder.add_edge("generate", END)

graph = builder.compile()

# ==========================================
# 4. Execution with Metadata
# ==========================================
if __name__ == "__main__":
    print(f"\n{'='*60}\n[Executing Agent Workflow with Metadata]")
    
    # THE OBSERVABILITY BOUNDARY
    # This config is passed into the graph. LangSmith automatically attaches
    # this data to the Root Run, and it cascades down to all child runs (LLMs, Tools).
    execution_config = {
        "run_name": "enterprise_knowledge_query",
        "tags": [
            "production",
            "rag",
            "customer-support"
        ],
        "metadata": {
            "environment": "production",
            "tenant_id": "tenant_42",
            "user_id": "user_123",
            "app_version": "1.8.2",
            "request_id": "req_88776655"
        }
    }
    
    result = graph.invoke(
        {"question": "What is the refund policy?", "retrieved_context": "", "answer": ""},
        config=execution_config
    )
    
    print("\n  [Final Answer]:")
    print(f"  {result['answer']}")
    print("\n  [System] Execution complete.")
    print("  Check the 'hello_smith' project in LangSmith!")
    print("  Notice the trace is named 'enterprise_knowledge_query' and contains your tags and metadata.")