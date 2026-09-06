from typing import Literal, Optional, TypedDict

from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import END, START, StateGraph


# ==========================================
# 1. State Schema
# ==========================================
class AgentState(TypedDict):
    scenario: str
    
    # We DO NOT put API keys in here!
    # Anything in here gets saved to the Checkpointer database.
    user_query: str
    proposed_tool: str
    
    final_output: str

# ==========================================
# 2. Nodes
# ==========================================
def llm_node(state: AgentState, config: RunnableConfig):
    """
    The LLM Agent. 
    Notice that the LLM is explicitly trying to steal the API key!
    """
    print(f"\n{'='*60}\n[Scenario]: {state['scenario']}")
    print("  [Agent] Booting up...")
    
    if state["scenario"] == "LLM Attempts to Steal Secret":
        # The LLM tries to read the secret from its own state context
        # But it's not there! It fails gracefully.
        stolen_key = state.get("STRIPE_API_KEY", "NOT_FOUND_IN_STATE")
        print(f"  [Agent] Malicious Request! Trying to print API Key: {stolen_key}")
        
    return {"proposed_tool": "refund_order"}

def tool_node(state: AgentState, config: RunnableConfig):
    """
    The safe Tool Execution layer.
    This python function reads the config, pulls the secret, and talks to Stripe.
    """
    tool = state["proposed_tool"]
    
    # Securely retrieve the secret injected by the backend
    secure_stripe_key = config["configurable"]["stripe_api_key"]
    
    print(f"  [Tool Node] Executing: {tool}()")
    print(f"  [Tool Node] Utilizing Secret Key: {secure_stripe_key[:4]}... (Redacted) to authenticate with external API.")
    
    # (Simulated API Call)
    return {"final_output": f"Refund processed securely using external API."}

# ==========================================
# 3. Build Graph
# ==========================================
builder = StateGraph(AgentState)
builder.add_node("llm", llm_node)
builder.add_node("tool", tool_node)

builder.add_edge(START, "llm")
builder.add_edge("llm", "tool")
builder.add_edge("tool", END)

graph = builder.compile()

# ==========================================
# 4. Backend Execution API
# ==========================================
def backend_api_call(scenario: str):
    # In a real app, this is pulled from AWS Secrets Manager or os.getenv
    REAL_STRIPE_SECRET = "sk_live_998877665544332211"
    
    # We securely inject it into LangGraph via config. 
    # It NEVER touches the `AgentState`.
    config = {
        "configurable": {
            "stripe_api_key": REAL_STRIPE_SECRET
        }
    }
    
    initial_state = {"scenario": scenario, "user_query": "Please refund order 123.", "proposed_tool": "", "final_output": ""}
    
    final_state = graph.invoke(initial_state, config=config)
    print(f"  [System Output]: {final_state['final_output']}")

# Run the scenario
backend_api_call("LLM Attempts to Steal Secret")