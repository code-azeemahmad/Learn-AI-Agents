import operator
import os
from pathlib import Path
from typing import Annotated, Literal, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
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
# 2. State Schema
# ==========================================
class AgentState(TypedDict):
    # Operator.add merges lists. 
    messages: Annotated[list[AnyMessage], operator.add]
    # We store the router's decision here so we can trace it!
    selected_agent: str

# ==========================================
# 3. Nodes
# ==========================================
def supervisor_node(state: AgentState):
    print("  [Supervisor] Analyzing request to determine routing...")
    messages = [
        SystemMessage(content="You are a router. Reply with exactly 'KNOWLEDGE' or 'SQL'."),
        HumanMessage(content=state["messages"][-1].content)
    ]
    response = llm.invoke(messages)
    decision = response.content.strip().upper()
    print(f"  [Supervisor] Decision: {decision}")
    
    # DELIBERATE BUG INTRODUCED HERE:
    # If the LLM says 'KNOWLEDGE', we accidentally store it as 'KNWLEDGE' (typo)
    if decision == "KNOWLEDGE":
        return {"selected_agent": "KNWLEDGE"}
    
    return {"selected_agent": decision}


def knowledge_agent_node(state: AgentState):
    print("  [Knowledge Agent] Fetching semantic documents...")
    return {"messages": [SystemMessage(content="Knowledge Agent executed.")]}

def sql_agent_node(state: AgentState):
    print("  [SQL Agent] Querying database...")
    return {"messages": [SystemMessage(content="SQL Agent executed.")]}

# ==========================================
# 4. Routing
# ==========================================
def router_edge(state: AgentState) -> Literal["knowledge", "sql"]:
    # The router reads the state variable to determine the next branch
    decision = state.get("selected_agent", "")
    
    if decision == "KNOWLEDGE":
        return "knowledge"
    elif decision == "SQL":
        return "sql"
    else:
        # LangGraph strictly validates edges. If the state doesn't match an edge, it crashes.
        raise ValueError(f"CRITICAL ROUTING ERROR: Unknown agent '{decision}'")

# ==========================================
# 5. Build Graph
# ==========================================
builder = StateGraph(AgentState)
builder.add_node("supervisor", supervisor_node)
builder.add_node("knowledge", knowledge_agent_node)
builder.add_node("sql", sql_agent_node)

builder.add_edge(START, "supervisor")
builder.add_conditional_edges("supervisor", router_edge)
builder.add_edge("knowledge", END)
builder.add_edge("sql", END)

graph = builder.compile()

# ==========================================
# 6. Execution
# ==========================================
if __name__ == "__main__":
    print(f"\n{'='*60}\n[Executing Buggy Workflow]")
    
    tracing_config = {
        "tags": ["bug_hunting", "multi_agent_routing"],
    }
    
    initial_state = {
        "messages": [HumanMessage(content="What is the company refund policy?")],
        "selected_agent": ""
    }
    
    try:
        graph.invoke(initial_state, config=tracing_config)
    except Exception as e:
        print(f"\n  [System Crashed!]: {e}")
        print("  [Debug Hint]: Open LangSmith. Click on the 'supervisor' node run.")
        print("  Look at the 'Output' tab for that specific node. What did it return?")