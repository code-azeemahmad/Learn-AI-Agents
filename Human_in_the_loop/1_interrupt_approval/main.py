from typing import Literal, Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


# ==========================================
# 1. State Schema
# ==========================================
class AgentState(TypedDict):
    scenario: str
    proposed_action: Optional[dict]
    approval_decision: Optional[dict]
    result: Optional[str]
    authorized_user: str

# ==========================================
# 2. Nodes
# ==========================================
def prepare_action_node(state: AgentState):
    """The Agent decides it wants to perform a high-risk action."""
    print(f"\n{'='*60}\n[Scenario]: {state['scenario']}")
    print("  [Agent] Analyzing request...")
    
    proposed = {
        "type": "delete_production_database",
        "target": "acme_corp_db",
        "reason": "Routine cleanup requested."
    }
    
    print(f"  [Agent] Proposing HIGH RISK action: {proposed['type']} on {proposed['target']}")
    return {"proposed_action": proposed}

def approval_node(state: AgentState):
    """
    The Hard Boundary.
    Execution pauses here. State is saved to the checkpointer.
    The graph yields control back to the caller.
    """
    action = state["proposed_action"]
    
    print("  [System] HIGH RISK ACTION DETECTED. Raising INTERRUPT.")
    
    # Execution literally stops here until a resume Command is received.
    human_response = interrupt({
        "message": "Approval required to execute destructive action.",
        "action": action
    })
    
    print(f"\n  [System] Waking up from INTERRUPT! Received response: {human_response}")
    return {"approval_decision": human_response}

def execute_action_node(state: AgentState):
    """Executes the action ONLY if approved."""
    action = state["proposed_action"]
    print(f"  [Execution] EXECUTING DESTRUCTIVE ACTION: {action['type']} on {action['target']}...")
    return {"result": f"Successfully executed: {action['type']}"}

# ==========================================
# 3. Router
# ==========================================
def route_approval(state: AgentState) -> Literal["execute_action", "__end__"]:
    decision = state["approval_decision"]
    
    # 1. Security Check: Did the right person approve it?
    if decision.get("user") != state["authorized_user"]:
        print(f"  [Router] SECURITY BREACH: '{decision.get('user')}' attempted to approve action belonging to '{state['authorized_user']}'. ABORTING.")
        return "__end__"
        
    # 2. Decision Check
    if decision.get("approved") is True:
        print("  [Router] Action Approved by authorized user. Routing to Execution.")
        return "execute_action"
        
    print("  [Router] Action Rejected by human. Aborting.")
    return "__end__"

# ==========================================
# 4. Build Graph with Checkpointer
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("prepare_action", prepare_action_node)
builder.add_node("approval", approval_node)
builder.add_node("execute_action", execute_action_node)

builder.add_edge(START, "prepare_action")
builder.add_edge("prepare_action", "approval")

# Route based on the human's resumed response
builder.add_conditional_edges("approval", route_approval)

builder.add_edge("execute_action", END)

# CRITICAL: HITL requires a checkpointer to save the state while paused
memory = MemorySaver()
graph = builder.compile(checkpointer=memory)

# ==========================================
# 5. Execution Simulation (The API Layer)
# ==========================================
def simulate_hitl_workflow(thread_id: str, scenario: str, human_response: dict):
    config = {"configurable": {"thread_id": thread_id}}
    
    # --- STEP 1: The Initial Request ---
    # The graph will run until it hits the interrupt(), then return.
    initial_state = {"scenario": scenario, "authorized_user": "admin_azeem", "proposed_action": None, "approval_decision": None, "result": None}
    
    for event in graph.stream(initial_state, config):
        pass # Consume the stream until it pauses
        
    print("  [API Layer] Graph execution paused. State persisted to DB. Awaiting human input...")
    
    # --- TIME PASSES (Could be 5 seconds or 5 days) ---
    
    # --- STEP 2: The Resume Request ---
    # We send a Command to the EXACT same thread_id to wake it up and pass the human's response
    print("  [API Layer] Human clicked a button on the UI. Resuming graph...")
    
    final_state = None
    for event in graph.stream(Command(resume=human_response), config):
        if "execute_action" in event:
            final_state = event["execute_action"]

# --- Run Scenarios ---
simulate_hitl_workflow(
    thread_id="thread-001", 
    scenario="Approve Path", 
    human_response={"approved": True, "user": "admin_azeem"}
)

simulate_hitl_workflow(
    thread_id="thread-002", 
    scenario="Reject Path", 
    human_response={"approved": False, "user": "admin_azeem"}
)

simulate_hitl_workflow(
    thread_id="thread-003", 
    scenario="Unauthorized User Attack", 
    human_response={"approved": True, "user": "malicious_hacker"}
)