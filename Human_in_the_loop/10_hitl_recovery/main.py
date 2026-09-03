from typing import TypedDict, Literal, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

# ==========================================
# 1. State Schema
# ==========================================
class AgentState(TypedDict):
    scenario: str
    action_payload: dict
    
    # Notice we keep these completely isolated!
    approval_status: Literal["pending", "approved", "rejected", "expired"]
    execution_status: Literal["not_started", "executing", "completed", "failed", "unknown"]
    recovery_status: Optional[str]
    
    action_version: int

# ==========================================
# 2. Nodes
# ==========================================
def prepare_node(state: AgentState) -> Command[Literal["approval_node"]]:
    print(f"\n{'='*60}\n[Scenario]: {state['scenario']}")
    print(f"  [Prepare] Requesting refund of $5,000. Version: {state['action_version']}")
    return Command(update={"approval_status": "pending"}, goto="approval_node")

def approval_node(state: AgentState) -> Command[Literal["execute_node", "terminal_node"]]:
    print("  [System] Interrupting execution. Waiting for manager approval...")
    decision = interrupt({"action_version": state["action_version"], "payload": state["action_payload"]})
    print(f"  [System] Resumed. Human decision: {decision['decision'].upper()}")
    
    # Simulating expiration logic
    if decision["decision"] == "expired":
        print("    -> The approval window closed. Marking EXPIRED.")
        return Command(update={"approval_status": "expired"}, goto="terminal_node")
        
    if decision["decision"] == "reject":
        print("    -> Human rejected the action.")
        return Command(update={"approval_status": "rejected"}, goto="terminal_node")
        
    return Command(update={"approval_status": "approved"}, goto="execute_node")

def execute_node(state: AgentState) -> Command[Literal["recovery_node", "terminal_node"]]:
    print(f"  [Execute] Approval Status is: {state['approval_status'].upper()}")
    print("  [Execute] Attempting to process refund...")
    
    # 1. Tampering Defense
    # The agent proposed a refund, but right before execution, we check if the world changed
    if state["scenario"] == "Payload Tampered":
        print("    -> VALIDATION FAILED! The action version changed during the approval window!")
        print("    -> Invalidating approval. Aborting execution.")
        return Command(update={"approval_status": "rejected", "execution_status": "failed"}, goto="terminal_node")

    # 2. Unknown Outcome Defense
    if state["scenario"] == "Tool Timeout":
        print("    -> HTTP 504 Gateway Timeout! Did the refund go through??")
        return Command(update={"execution_status": "unknown", "recovery_status": "verifying"}, goto="recovery_node")
        
    print("    -> Refund processed successfully.")
    return Command(update={"execution_status": "completed"}, goto="terminal_node")

def recovery_node(state: AgentState) -> Command[Literal["terminal_node"]]:
    """Isolates the execution failure without touching the approval state."""
    print(f"  [Recovery] Isolating Execution Failure. Current Status: {state['execution_status'].upper()}")
    print("  [Recovery] Checking upstream payment provider...")
    print("  [Recovery] Payment provider confirms refund was processed despite the timeout.")
    return Command(update={"execution_status": "completed", "recovery_status": "recovered"}, goto="terminal_node")

def terminal_node(state: AgentState):
    print(f"  [Terminal] Workflow shutting down. Approval: {state['approval_status'].upper()} | Execution: {state['execution_status'].upper()}")
    return {}

# ==========================================
# 3. Build Graph
# ==========================================
builder = StateGraph(AgentState)

# FIXED: Node names updated to exactly match the `goto=` targets
builder.add_node("prepare_node", prepare_node)
builder.add_node("approval_node", approval_node)
builder.add_node("execute_node", execute_node)
builder.add_node("recovery_node", recovery_node)
builder.add_node("terminal_node", terminal_node)

builder.add_edge(START, "prepare_node")
builder.add_edge("terminal_node", END)

memory = MemorySaver()
graph = builder.compile(checkpointer=memory)

# ==========================================
# 4. Execution Simulation
# ==========================================
def simulate_hitl_recovery(thread_id: str, scenario: str, human_payload: dict, modify_state_during_pause: bool = False):
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {
        "scenario": scenario, "action_version": 1, "action_payload": {"amount": 5000},
        "approval_status": "pending", "execution_status": "not_started", "recovery_status": None
    }
    
    for _ in graph.stream(initial_state, config): pass
    
    # Simulating a bad actor changing the DB payload while the graph is paused waiting for the manager!
    if modify_state_during_pause:
        graph.update_state(config, {"action_version": 2, "action_payload": {"amount": 50000}})
        
    graph.invoke(Command(resume=human_payload), config)

# Run Scenarios
simulate_hitl_recovery("thread-1", "Approval Expired", {"decision": "expired", "action_version": 1})
simulate_hitl_recovery("thread-2", "Tool Timeout", {"decision": "approve", "action_version": 1})
simulate_hitl_recovery("thread-3", "Payload Tampered", {"decision": "approve", "action_version": 1}, modify_state_during_pause=True)