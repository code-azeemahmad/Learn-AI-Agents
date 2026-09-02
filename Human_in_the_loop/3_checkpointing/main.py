from typing import Literal, Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


# ==========================================
# 1. State Schema
# ==========================================
class AgentState(TypedDict):
    task: str
    approved: Optional[bool]
    result: Optional[str]

# ==========================================
# 2. Nodes
# ==========================================
def prepare_node(state: AgentState):
    print(f"\n  [Node] Preparing task: '{state['task']}'")
    return {"result": "Task Prepared"}

def approval_node(state: AgentState):
    print("  [Node] Hitting the interrupt boundary...")
    
    # Execution pauses here. The Checkpointer saves the state to DB.
    approved = interrupt({
        "type": "approval_required",
        "task": state["task"]
    })
    
    print(f"  [Node] Resumed! Received decision: {approved}")
    return {"approved": approved}

def execute_node(state: AgentState):
    if state.get("approved"):
        print("  [Node] Executing task...")
        return {"result": "Action executed successfully."}
    
    print("  [Node] Task rejected.")
    return {"result": "Action rejected."}

# ==========================================
# 3. Build Graph with Checkpointer
# ==========================================
builder = StateGraph(AgentState)
builder.add_node("prepare", prepare_node)
builder.add_node("approval", approval_node)
builder.add_node("execute", execute_node)

builder.add_edge(START, "prepare")
builder.add_edge("prepare", "approval")
builder.add_edge("approval", "execute")
builder.add_edge("execute", END)

# The Checkpointer is the engine of HITL. Without it, interrupt() fails.
checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer)

# ==========================================
# 4. Simulation Engine
# ==========================================
def run_simulation():
    thread_id = "refund-123"
    config = {"configurable": {"thread_id": thread_id}}
    
    print(f"\n{'='*60}\n=== PHASE 1: INITIAL INVOCATION ===\n{'='*60}")
    print(f"  [API] Starting thread: {thread_id}")
    
    initial_state = {"task": "Refund order #123", "approved": None, "result": ""}
    
    # We use stream() to easily catch the interrupt event
    for event in graph.stream(initial_state, config):
        if "__interrupt__" in event:
            # Note: in stream(), the interrupt data is yielded as an event
            payload = event["__interrupt__"][0].value
            print(f"  [API] Graph execution paused. Interrupt Payload: {payload}")
            print("  [API] Checkpointer has persisted the state. Exiting process.")
            break
            
    print(f"\n{'='*60}\n=== PHASE 2: RESUMPTION ===\n{'='*60}")
    print("  [API] 2 hours later...")
    print(f"  [API] Manager clicked 'Approve'. Resuming thread: {thread_id}")
    
    # We resume by sending a Command to the EXACT SAME thread_id
    # The Checkpointer pulls the state from memory and injects the Command
    for event in graph.stream(Command(resume=True), config):
        pass
        
    # Let's check the final persisted state in the checkpointer
    final_state = graph.get_state(config).values
    print(f"\n  [API] Final State Result: {final_state.get('result')}")

run_simulation()