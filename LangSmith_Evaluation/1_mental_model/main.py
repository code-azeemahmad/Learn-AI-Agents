import os
from pathlib import Path
from typing import Literal, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph

os.environ["LANGSMITH_PROJECT"] = "mental_model"

# ==========================================
# 1. Environment Configuration
# ==========================================
# Explicitly load the .env from your target directory
ENV_PATH = Path(r"F:\ai_agents_langgraph\Learn-AI-Agents\LangSmith_Evaluation\.env")
load_dotenv(dotenv_path=ENV_PATH)

# ==========================================
# 2. Provider Initialization (Ollama)
# ==========================================
model_name = os.getenv("OLLAMA_MODEL_NAME", "gemma4:26b")
llm = ChatOllama(
    model=model_name,
    base_url="http://localhost:11434/",
    temperature=0,
)

# ==========================================
# 3. State Schema & Nodes
# ==========================================
class AgentState(TypedDict):
    user_query: str
    tool_called: bool
    final_answer: str

def supervisor_node(state: AgentState):
    print("  [Supervisor] Analyzing request using Ollama...")
    
    # We invoke the LLM here. Because LANGSMITH_TRACING=true is in your .env,
    # this LLM call will be perfectly nested inside the LangGraph trace!
    messages = [
        SystemMessage(content="You are a routing supervisor. Simply reply with 'ROUTE_TO_KNOWLEDGE'."),
        HumanMessage(content=state["user_query"])
    ]
    response = llm.invoke(messages)
    print(f"  [Supervisor] LLM Decision: {response.content.strip()}")
    
    return {"tool_called": True}

def knowledge_retrieval_node(state: AgentState):
    print("  [Knowledge Tool] Fetching documents from Qdrant...")
    return {"final_answer": "Refunds are processed within 30 days."}

# ==========================================
# 4. Build Graph
# ==========================================
builder = StateGraph(AgentState)
builder.add_node("supervisor", supervisor_node)
builder.add_node("retrieval", knowledge_retrieval_node)

builder.add_edge(START, "supervisor")
builder.add_edge("supervisor", "retrieval")
builder.add_edge("retrieval", END)

graph = builder.compile()

# ==========================================
# 5. Execution
# ==========================================
if __name__ == "__main__":
    print(f"\n{'='*60}\n[Executing Agent Workflow]")
    
    # This invocation is automatically captured as a LangSmith Trace!
    result = graph.invoke({
        "user_query": "What is the refund policy?", 
        "tool_called": False, 
        "final_answer": ""
    })
    
    print("\n  [System] Final Output:")
    print(f"  {result['final_answer']}")
    print("\n  [System] Execution complete. Check the 'hello_smith' project in LangSmith!")