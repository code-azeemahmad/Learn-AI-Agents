import operator
from typing import Annotated, Literal, TypedDict

from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph


# ==========================================
# 1. State Schema
# ==========================================
class AgentState(TypedDict):
    # We use a simple list of strings to represent the conversation/scratchpad
    messages: Annotated[list[str], operator.add]
    current_agent: str

# ==========================================
# 2. Specialized Sub-Agents (Wrapped as Tools)
# ==========================================
# In a real app, these would be their own separate LangGraph workflows or LLM chains
@tool
def research_agent(query: str) -> str:
    """Pass complex technical or documentation questions to the Research Specialist."""
    print(f"\n    [Sub-Agent: Research] Booting up specialized context...")
    print(f"    [Sub-Agent: Research] Searching internal docs for: '{query}'")
    # Simulate an LLM searching docs
    return "Research Result: Qdrant replication requires at least 2 nodes."

@tool
def billing_agent(customer_id: str) -> str:
    """Pass invoice, refund, or payment questions to the Billing Specialist."""
    print(f"\n    [Sub-Agent: Billing] Booting up secure financial context...")
    print(f"    [Sub-Agent: Billing] Accessing Stripe API for customer: '{customer_id}'")
    # Simulate an LLM accessing secure financial data
    return "Billing Result: Invoice #998 is 30 days overdue."

# A dictionary so our router can dynamically call the tool based on the string name
AVAILABLE_TOOLS = {
    "research_agent": research_agent,
    "billing_agent": billing_agent
}

# ==========================================
# 3. Supervisor Node
# ==========================================
def supervisor_node(state: AgentState):
    """
    The Supervisor reads the user's request and decides which specialized agent to deploy.
    In a real app, this is an LLM with tool-calling enabled. We simulate the LLM's reasoning here.
    """
    user_query = state["messages"][0]
    print(f"\n{'='*60}\n[User]: {user_query}")
    print("  [Supervisor] Analyzing intent to determine correct routing...")
    
    # Simulating LLM Tool-Calling Logic
    if "invoice" in user_query.lower() or "billing" in user_query.lower():
        print("  [Supervisor] Decision: This is a financial query. Delegating to Billing Agent.")
        return {"messages": ["CALL_TOOL:billing_agent|cust_123"]}
        
    elif "docs" in user_query.lower() or "how" in user_query.lower():
        print("  [Supervisor] Decision: This is a technical query. Delegating to Research Agent.")
        return {"messages": ["CALL_TOOL:research_agent|Qdrant"] }
        
    else:
        print("  [Supervisor] Decision: I can handle this myself without sub-agents.")
        return {"messages": ["I am an AI assistant. How can I help you today?"]}

# ==========================================
# 4. Tool Execution Node
# ==========================================
def tool_node(state: AgentState):
    """Executes the sub-agent requested by the Supervisor."""
    last_message = state["messages"][-1]
    
    # Parse our simulated tool call (e.g., "CALL_TOOL:billing_agent|cust_123")
    _, payload = last_message.split(":")
    tool_name, arg = payload.split("|")
    
    # Execute the sub-agent!
    tool_func = AVAILABLE_TOOLS[tool_name]
    result = tool_func.invoke(arg)
    
    print(f"    [Tool Node] Sub-Agent returned: '{result}'")
    return {"messages": [f"TOOL_RESULT:{result}"]}

# ==========================================
# 5. Synthesis Node
# ==========================================
def synthesis_node(state: AgentState):
    """The Supervisor takes the result from the sub-agent and answers the user."""
    tool_result = state["messages"][-1].replace("TOOL_RESULT:", "")
    print(f"  [Supervisor] Synthesizing final answer based on sub-agent data...")
    print(f"  [Supervisor Final Output]: Based on the internal systems, {tool_result.lower()}")
    return {"messages": ["Final Answer Generated."]}

# ==========================================
# 6. Edge Routing
# ==========================================
def should_continue(state: AgentState) -> Literal["tool_node", "__end__"]:
    """Determines if the Supervisor called a tool, or just answered directly."""
    last_message = state["messages"][-1]
    if last_message.startswith("CALL_TOOL:"):
        return "tool_node"
    return "__end__"

# ==========================================
# 7. Build Graph
# ==========================================
builder = StateGraph(AgentState)
builder.add_node("supervisor", supervisor_node)
builder.add_node("tool_node", tool_node)
builder.add_node("synthesis", synthesis_node)

builder.add_edge(START, "supervisor")
builder.add_conditional_edges("supervisor", should_continue)
builder.add_edge("tool_node", "synthesis") # Send tool result back to the Supervisor for synthesis
builder.add_edge("synthesis", END)

graph = builder.compile()

# ==========================================
# 8. Execution Scenarios
# ==========================================
def run(query: str):
    graph.invoke({"messages": [query], "current_agent": "supervisor"})

run("Why was my invoice rejected?")
run("How does Qdrant replication work according to the docs?")
run("Hello, who are you?")