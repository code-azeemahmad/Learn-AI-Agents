from typing import Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph


# ==========================================
# 1. State Schema
# ==========================================
class AgentState(TypedDict):
    scenario: str
    user_request: str
    
    # The magical state variable that controls the handoff!
    active_agent: Literal["support", "billing", "technical"]
    
    # The structured summary passed during the handoff
    handoff_context: Optional[dict]
    
    final_output: Optional[str]

# ==========================================
# 2. Handoff Tools (Simulated)
# ==========================================
# In a real app, these are @tool annotated functions the LLM calls
def tool_transfer_to_billing(customer_id: str, issue_summary: str) -> dict:
    print(f"    [Tool Executed] Initiating Handoff to Billing...")
    return {
        "active_agent": "billing", 
        "handoff_context": {"customer": customer_id, "summary": issue_summary}
    }

def tool_transfer_to_technical(issue_summary: str) -> dict:
    print(f"    [Tool Executed] Initiating Handoff to Technical...")
    return {
        "active_agent": "technical", 
        "handoff_context": {"summary": issue_summary}
    }

# ==========================================
# 3. Agent Nodes
# ==========================================
def support_agent_node(state: AgentState):
    """The frontline agent."""
    print(f"\n{'='*60}\n[User]: {state['user_request']}")
    print("  [Support Agent] Analyzing request...")
    
    request = state["user_request"].lower()
    
    if "refund" in request or "invoice" in request:
        print("  [Support Agent] I can't handle financial disputes. Calling transfer_to_billing().")
        # The agent returns state updates, triggering the handoff
        return tool_transfer_to_billing(customer_id="Cust-992", issue_summary=request)
        
    elif "broken" in request or "error" in request:
        print("  [Support Agent] This sounds like a bug. Calling transfer_to_technical().")
        return tool_transfer_to_technical(issue_summary=request)
        
    else:
        print("  [Support Agent] I can handle this directly!")
        return {"final_output": "I am happy to help you update your profile picture."}

def billing_agent_node(state: AgentState):
    """The specialist."""
    print(f"  [Billing Agent] I have taken over the chat. Reviewing handoff context: {state['handoff_context']}")
    print("  [Billing Agent] Checking Stripe database...")
    return {"final_output": "I see you requested a refund. I have processed it to your original payment method."}

def technical_agent_node(state: AgentState):
    """The specialist."""
    print(f"  [Technical Agent] I have taken over the chat. Reviewing handoff context: {state['handoff_context']}")
    print("  [Technical Agent] Checking Datadog logs...")
    return {"final_output": "I see the 500 error in the logs. I have escalated this to engineering."}

# ==========================================
# 4. The Handoff Router
# ==========================================
def route_active_agent(state: AgentState) -> Literal["support_agent", "billing_agent", "technical_agent", "__end__"]:
    """
    This edge runs after EVERY node. It checks if the active_agent changed.
    If the agent finished the chat, we route to END.
    If the agent changed the `active_agent` state, we route to the new agent!
    """
    if state.get("final_output"):
        return "__end__"
        
    active = state["active_agent"]
    if active == "billing": return "billing_agent"
    if active == "technical": return "technical_agent"
    return "support_agent"

# ==========================================
# 5. Build Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("support_agent", support_agent_node)
builder.add_node("billing_agent", billing_agent_node)
builder.add_node("technical_agent", technical_agent_node)

builder.add_edge(START, "support_agent")

# The router sits between the agents, evaluating the state to determine where to go next
builder.add_conditional_edges("support_agent", route_active_agent)
builder.add_conditional_edges("billing_agent", route_active_agent)
builder.add_conditional_edges("technical_agent", route_active_agent)

graph = builder.compile()

# ==========================================
# 6. Execution Scenarios
# ==========================================
def run(scenario: str, request: str):
    initial_state = {"scenario": scenario, "user_request": request, "active_agent": "support", "handoff_context": None, "final_output": None}
    final_state = graph.invoke(initial_state)
    print(f"  [Final System Output]: {final_state['final_output']}")

run("Standard Support", "How do I change my profile picture?")
run("Billing Handoff", "I need a refund for my last invoice!")
run("Technical Handoff", "The app is throwing a 500 error.")