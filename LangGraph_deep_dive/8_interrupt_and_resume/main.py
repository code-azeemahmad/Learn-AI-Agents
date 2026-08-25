from typing import Optional

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict


# ==========================================
# 1. State Schema
# ==========================================
class State(TypedDict):
    action: str
    approved: bool
    result: str
    reason: Optional[str]  # Added to support structured responses  # noqa: UP045

# ==========================================
# 2. Nodes
# ==========================================
def prepare_action(state: State):
    print("  [Node: prepare_action] Proposing risky action...")
    return {"action": "delete user 123"}

def approval(state: State):
    print("  [Node: approval] ---> Node started/restarted.")
    
    # Pause execution here. The payload is sent to the caller.
    human_decision = interrupt({
        "action": state["action"],
        "question": "Do you approve this action?"
    })
    
    print(f"  [Node: approval] ---> Resumed with input: {human_decision}")
    
    # Parse the resume payload (Handles both boolean and structured dicts)
    if isinstance(human_decision, dict):
        return {
            "approved": human_decision.get("decision") == "approve",
            "reason": human_decision.get("reason", "No reason provided")
        }
    else:
        return {
            "approved": bool(human_decision),
            "reason": "Simple boolean response"
        }

def execute_action(state: State):
    if state.get("approved"):
        print(f"  [Node: execute_action] EXECUTING: {state['action']}")
        return {"result": f"Action approved and executed. ({state.get('reason')})"}
    else:
        print(f"  [Node: execute_action] ABORTING: {state['action']}")
        return {"result": f"Action rejected. ({state.get('reason')})"}

# ==========================================
# 3. Build & Compile
# ==========================================
builder = StateGraph(State)
builder.add_node("prepare_action", prepare_action)
builder.add_node("approval", approval)
builder.add_node("execute_action", execute_action)

builder.add_edge(START, "prepare_action")
builder.add_edge("prepare_action", "approval")
builder.add_edge("approval", "execute_action")
builder.add_edge("execute_action", END)

graph = builder.compile(checkpointer=InMemorySaver())

# ==========================================
# 4. Execution Tests
# ==========================================

print("\n=== TEST CASE 1: Simple Approve ===")
config_1 = {"configurable": {"thread_id": "thread-1"}}

# Step 1: Start graph -> Hits interrupt
print("--- Initial Run ---")
graph.invoke({"action": "", "approved": False, "result": ""}, config_1)

# Step 2: Human clicks "Yes" -> Resume
print("\n--- Resuming Run ---")
result_1 = graph.invoke(Command(resume=True), config_1)
print(f"Final State: {result_1['result']}")


print("\n=== TEST CASE 2: Simple Reject ===")
config_2 = {"configurable": {"thread_id": "thread-2"}}

print("--- Initial Run ---")
graph.invoke({"action": "", "approved": False, "result": ""}, config_2)

print("\n--- Resuming Run ---")
result_2 = graph.invoke(Command(resume=False), config_2)
print(f"Final State: {result_2['result']}")


print("\n=== TEST CASE 3: Structured Decision ===")
config_3 = {"configurable": {"thread_id": "thread-3"}}

print("--- Initial Run ---")
graph.invoke({"action": "", "approved": False, "result": ""}, config_3)

print("\n--- Resuming Run ---")
result_3 = graph.invoke(Command(resume={
    "decision": "approve",
    "reason": "Reviewed manually by Admin ID 99"
}), config_3)
print(f"Final State: {result_3['result']}")