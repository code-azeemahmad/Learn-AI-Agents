from typing import Literal, Optional, Tuple, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

# ==========================================
# 1. State Machine Schema Definition
# ==========================================
# These are the ONLY legal states in our domain
WorkflowStatus = Literal[
    "pending",
    "in_review",
    "approved",
    "rejected",
    "executing",
    "completed",
    "failed"
]

class AgentState(TypedDict):
    scenario: str
    action_version: int
    status: WorkflowStatus

# ==========================================
# 2. Strict Transition Engine
# ==========================================
# Define the exact matrix of what state can move to what state
TRANSITIONS = {
    ("pending", "start_review"): "in_review",
    ("in_review", "approve"): "approved",
    ("in_review", "reject"): "rejected",
    ("approved", "execute"): "executing",
    ("executing", "success"): "completed",
    ("executing", "failure"): "failed",
}

def get_next_state(current_state: str, event: str) -> str:
    """The gatekeeper: throws an exception if the transition is illegal."""
    next_state = TRANSITIONS.get((current_state, event))
    if not next_state:
        raise ValueError(f"ILLEGAL STATE TRANSITION: Cannot move from '{current_state}' via event '{event}'.")
    return next_state

# ==========================================
# 3. Graph Nodes
# ==========================================
def prepare_node(state: AgentState) -> Command[Literal["approval_node"]]:
    print(f"\n{'='*60}\n[Scenario]: {state['scenario']}")
    
    # 1. Legal Transition: pending -> in_review
    next_status = get_next_state(state["status"], "start_review")
    print(f"  [Prepare] Agent proposes action v{state['action_version']}. Status moving to: {next_status.upper()}")
    
    return Command(update={"status": next_status}, goto="approval_node")


def approval_node(state: AgentState) -> Command[Literal["execute_node", "terminal_node"]]:
    print("  [System] Interrupting execution. Entering IN_REVIEW state...")
    decision = interrupt({"action_version": state["action_version"], "status": state["status"]})
    print(f"  [System] Woke up! Human decision event: '{decision['event'].upper()}'")
    
    # 2. Security Check: Action Versioning
    if decision["action_version"] != state["action_version"]:
        print(f"    -> VERSION MISMATCH: The human approved v{decision['action_version']}, but the agent is executing v{state['action_version']}! Forcing REJECT.")
        next_status = get_next_state(state["status"], "reject")
        return Command(update={"status": next_status}, goto="terminal_node")
    
    # 3. Attempt the legal transition based on the human event (approve | reject)
    try:
        next_status = get_next_state(state["status"], decision["event"])
        print(f"    -> Legal Transition! Status moving to: {next_status.upper()}")
        
        goto_target = "execute_node" if next_status == "approved" else "terminal_node"
        return Command(update={"status": next_status}, goto=goto_target)
        
    except ValueError as e:
        print(f"    -> {str(e)}")
        return Command(update={"status": "failed"}, goto="terminal_node")


def execute_node(state: AgentState) -> Command[Literal["terminal_node"]]:
    # 4. Legal Transition: approved -> executing
    exec_status = get_next_state(state["status"], "execute")
    print(f"  [Execute] Status moving to: {exec_status.upper()}")
    print("  [Execute] Running destructive side-effect...")
    
    # 5. Final Legal Transition: executing -> completed
    final_status = get_next_state(exec_status, "success")
    return Command(update={"status": final_status}, goto="terminal_node")


def terminal_node(state: AgentState):
    print(f"  [Terminal] Workflow shutting down in state: {state['status'].upper()}")
    return {}

# ==========================================
# 4. Build Graph
# ==========================================
builder = StateGraph(AgentState)

# FIXED: Re-named the nodes to properly match the `goto=` targets in the Command responses
builder.add_node("prepare_node", prepare_node)
builder.add_node("approval_node", approval_node)
builder.add_node("execute_node", execute_node)
builder.add_node("terminal_node", terminal_node)

builder.add_edge(START, "prepare_node")
builder.add_edge("terminal_node", END)

memory = MemorySaver()
graph = builder.compile(checkpointer=memory)

# ==========================================
# 5. Execution Simulation
# ==========================================
def simulate_state_machine(thread_id: str, scenario: str, human_payload: dict):
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {"scenario": scenario, "action_version": 1, "status": "pending"}
    
    for _ in graph.stream(initial_state, config): pass
    graph.invoke(Command(resume=human_payload), config)

# 1. Standard Happy Path (pending -> in_review -> approved -> executing -> completed)
simulate_state_machine("thread-A", "Happy Path", {"event": "approve", "action_version": 1})

# 2. Standard Rejection (pending -> in_review -> rejected)
simulate_state_machine("thread-B", "Human Rejection", {"event": "reject", "action_version": 1})

# 3. The Security Catch (The action changed while the human was reviewing it!)
simulate_state_machine("thread-C", "Action Version Mismatch", {"event": "approve", "action_version": 2})

# 4. The Illegal Transition Attack (Trying to jump from in_review -> success)
simulate_state_machine("thread-D", "Illegal Transition Attack", {"event": "success", "action_version": 1})