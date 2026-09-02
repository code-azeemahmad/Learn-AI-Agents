from typing import Literal, Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


# ==========================================
# 1. State Schema
# ==========================================
class AgentState(TypedDict):
    scenario: str
    collection: str
    document_count: int
    status: Literal["pending", "approved", "rejected", "executed", "cancelled"]

# ==========================================
# 2. Nodes
# ==========================================
def prepare_deletion_node(state: AgentState):
    """The Agent prepares the dangerous payload."""
    print(f"\n{'='*60}\n[Scenario]: {state['scenario']}")
    print(f"  [Prepare] Agent proposes deleting {state['document_count']} documents from '{state['collection']}'.")
    return {"status": "pending"}

def approval_node(state: AgentState) -> Command[Literal["execute_node", "cancel_node"]]:
    """
    The HITL Boundary. 
    Returns a Command object to dynamically route the graph based on human input.
    """
    print("  [System] Pausing execution for human review...")
    
    # 1. Pause and send payload to frontend
    human_response = interrupt({
        "type": "approval_request",
        "action": "delete_documents",
        "collection": state["collection"],
        "document_count": state["document_count"],
        "message": f"Approve deletion of {state['document_count']} documents in '{state['collection']}'?"
    })
    
    # 2. Execution resumes here! Process the human's decision.
    decision = human_response.get("decision")
    print(f"  [System] Resumed! Human decision: '{decision.upper()}'")
    
    if decision == "approve":
        print("    -> Action approved as proposed.")
        return Command(
            update={"status": "approved"}, 
            goto="execute_node"
        )
        
    elif decision == "modify":
        new_count = human_response.get("new_count")
        print(f"    -> Action approved WITH MODIFICATIONS. Changing count from {state['document_count']} to {new_count}.")
        return Command(
            # We actively mutate the state based on human input before executing!
            update={"document_count": new_count, "status": "approved"}, 
            goto="execute_node"
        )
        
    else:
        print("    -> Action rejected.")
        return Command(
            update={"status": "rejected"}, 
            goto="cancel_node"
        )

def execute_node(state: AgentState):
    """Executes the side-effect (guaranteed to happen AFTER approval)."""
    print(f"  [Execution] DELETING {state['document_count']} documents from '{state['collection']}'...")
    return {"status": "executed"}

def cancel_node(state: AgentState):
    print("  [Execution] Operation cancelled. No documents deleted.")
    return {"status": "cancelled"}

# ==========================================
# 3. Build Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("prepare", prepare_deletion_node)
builder.add_node("approval", approval_node)
builder.add_node("execute_node", execute_node)
builder.add_node("cancel_node", cancel_node)

builder.add_edge(START, "prepare")
builder.add_edge("prepare", "approval")
# Note: We do NOT need add_conditional_edges here because approval_node returns a Command!
builder.add_edge("execute_node", END)
builder.add_edge("cancel_node", END)

memory = MemorySaver()
graph = builder.compile(checkpointer=memory)

# ==========================================
# 4. Simulation Engine
# ==========================================
def simulate_approval_workflow(thread_id: str, scenario: str, human_payload: dict):
    config = {"configurable": {"thread_id": thread_id}}
    
    # --- STEP 1: Run to Interrupt ---
    initial_state = {
        "scenario": scenario, "collection": "finance_records", 
        "document_count": 1842, "status": "pending"
    }
    
    for event in graph.stream(initial_state, config):
        pass # Stream until paused
        
    # --- STEP 2: Resume with Human Payload ---
    final_state = graph.invoke(Command(resume=human_payload), config)
    print(f"  [API] Final Workflow Status: {final_state['status'].upper()}")


# Run Scenarios
simulate_approval_workflow(
    thread_id="thread-A", 
    scenario="Binary Approval", 
    human_payload={"decision": "approve"}
)

simulate_approval_workflow(
    thread_id="thread-B", 
    scenario="Binary Rejection", 
    human_payload={"decision": "reject"}
)

simulate_approval_workflow(
    thread_id="thread-C", 
    scenario="Approve WITH Modification", 
    human_payload={"decision": "modify", "new_count": 50} # Human intervenes to save 1,792 documents!
)