import operator
import os
from pathlib import Path
from typing import Annotated, TypedDict

import langsmith as ls
from dotenv import load_dotenv
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

# ==========================================
# 1. Environment Configuration
# ==========================================
ENV_PATH = Path(r"F:\ai_agents_langgraph\Learn-AI-Agents\LangSmith_Evaluation\.env")
load_dotenv(dotenv_path=ENV_PATH)

model_name = os.getenv("OLLAMA_MODEL_NAME", "gemma4:26b")
llm = ChatOllama(model=model_name, base_url="http://localhost:11434/")

# ==========================================
# 2. Tools (Automatically Traced)
# ==========================================
@tool
def calculate_tax(amount: float, tax_rate: float) -> float:
    """Calculates the final price after tax."""
    print(f"  [Tool Executed] calculate_tax({amount}, {tax_rate})")
    return amount + (amount * tax_rate)

tools = [calculate_tax]
llm_with_tools = llm.bind_tools(tools)

# ==========================================
# 3. State Schema
# ==========================================
# FIXED: We use a reducer (operator.add) so messages append instead of overwrite.
class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]

# ==========================================
# 4. Nodes
# ==========================================
def agent_node(state: AgentState):
    print("  [Agent] Reasoning...")
    
    # We dynamically prepend the system instructions to the message history
    messages = state["messages"]
    if not any(isinstance(m, SystemMessage) for m in messages):
        messages = [SystemMessage(content="You are a financial assistant. Use tools to calculate math.")] + messages
        
    response = llm_with_tools.invoke(messages)
    
    # Returning this will APPEND the response to the state, not overwrite it!
    return {"messages": [response]}

# ==========================================
# 5. Routing
# ==========================================
def should_continue(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        print("  [Router] LLM requested a tool call. Routing to ToolNode.")
        return "tools"
    print("  [Router] LLM provided final answer. Ending.")
    return END

# ==========================================
# 6. Build Graph
# ==========================================
builder = StateGraph(AgentState)
builder.add_node("agent", agent_node)
builder.add_node("tools", ToolNode(tools)) 

builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", should_continue)
builder.add_edge("tools", "agent")

graph = builder.compile()

# ==========================================
# 7. Execution with Telemetry Metadata
# ==========================================
if __name__ == "__main__":
    print(f"\n{'='*60}\n[Executing Agent Workflow]")
    
    tracing_config = {
        "tags": ["finance_agent", "v1", "learning"],
        "metadata": {
            "environment": "local_dev",
            "user_segment": "premium"
        }
    }
    
    # We seed the state with the initial HumanMessage
    initial_state = {
        "messages": [HumanMessage(content="What is the total price of a $500 order with 8% tax?")]
    }
    
    result = graph.invoke(initial_state, config=tracing_config)
    
    print("\n  [Final Answer]:")
    print(result["messages"][-1].content)

    # selective tracing around an operation
    with ls.tracing_context(
        project_name="special-debug-run",
        enabled=True,
    ):
        response = llm.invoke(
            "Explain BM25 in five lines."
        )
        print(response.content)