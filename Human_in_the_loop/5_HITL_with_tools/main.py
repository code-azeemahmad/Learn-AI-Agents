from typing import List, Literal, Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


# ==========================================
# 1. State Schema
# ==========================================
class AgentState(TypedDict):
    scenario: str
    tool_to_call: str
    tool_args: dict
    tool_result: Optional[str]

# ==========================================
# 2. Simulated LLM Node
# ==========================================
def llm_node(state: AgentState):
    """Simulates an LLM choosing to call a tool based on the scenario."""
    print(f"\n{'='*60}\n[Scenario]: {state['scenario']}")
    print("  [LLM] Reasoning...")
    
    if state["scenario"] == "Safe Tool":
        tool = "search_documents"
        args = {"query": "Qdrant vector database tuning"}
    else:
        # LLM proposes sending an email
        tool = "send_email"
        args = {
            "recipient": "alice@example.com",
            "subject": "Deployment Update",
            "body": "The deployment has finished successfully."
        }
        
    print(f"  [LLM] Decided to call tool: '{tool}' with args: {args}")
    return {"tool_to_call": tool, "tool_args": args}

# ==========================================
# 3. Tool Nodes
# ==========================================
def search_documents_tool_node(state: AgentState):
    """LOW RISK: Executes instantly without Human Approval."""
    print(f"  [Tool: Search] Executing safe read-only operation...")
    print(f"    -> Searching for: {state['tool_args']['query']}")
    return {"tool_result": "Found 3 relevant documents."}

def send_email_tool_node(state: AgentState):
    """HIGH RISK: Protects itself by forcing an interrupt BEFORE side-effects."""
    args = state["tool_args"]
    print(f"  [Tool: Email] DANGEROUS TOOL CALLED. Raising interrupt.")
    
    # Execution pauses here. Payload sent to the frontend.
    decision = interrupt({
        "type": "tool_approval",
        "tool": "send_email",
        "proposed_args": args,
        "message": f"Approve sending email to {args['recipient']}?"
    })
    
    print(f"  [Tool: Email] Woke up! Processing human decision: {decision['action'].upper()}")
    
    if decision["action"] == "reject":
        print("    -> Email cancelled by human.")
        return {"tool_result": "Error: User rejected the tool call."}
        
    # Check if the human edited the arguments
    final_recipient = decision.get("edited_recipient", args["recipient"])
    
    if final_recipient != args["recipient"]:
        print(f"    -> ARGUMENTS MODIFIED: Changing recipient from '{args['recipient']}' to '{final_recipient}'.")
        
    # ====== THE DANGEROUS SIDE EFFECT HAPPENS HERE ======
    print(f"    -> SENDING EMAIL to {final_recipient}: '{args['subject']}'")
    # ====================================================
    
    return {"tool_result": f"Success: Email sent to {final_recipient}."}

# ==========================================
# 4. Routers
# ==========================================
def route_tool_call(state: AgentState) -> Literal["search_documents_tool_node", "send_email_tool_node"]:
    """Routes the LLM's request to the correct tool node."""
    if state["tool_to_call"] == "search_documents":
        return "search_documents_tool_node"
    return "send_email_tool_node"

def llm_feedback_node(state: AgentState):
    """Simulates the LLM receiving the final tool output."""
    print(f"  [LLM] Received Tool Output: '{state['tool_result']}'")
    return {}

# ==========================================
# 5. Build Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("llm", llm_node)
builder.add_node("search_documents_tool_node", search_documents_tool_node)
builder.add_node("send_email_tool_node", send_email_tool_node)
builder.add_node("llm_feedback", llm_feedback_node)

builder.add_edge(START, "llm")
builder.add_conditional_edges("llm", route_tool_call)

# Both tools return to the LLM so it can read the result
builder.add_edge("search_documents_tool_node", "llm_feedback")
builder.add_edge("send_email_tool_node", "llm_feedback")
builder.add_edge("llm_feedback", END)

memory = MemorySaver()
graph = builder.compile(checkpointer=memory)

# ==========================================
# 6. Execution Simulation
# ==========================================
def run_simulation(thread_id: str, scenario: str, human_payload: dict = None):
    config = {"configurable": {"thread_id": thread_id}}
    
    # --- PHASE 1: Run to Interrupt (or completion) ---
    initial_state = {"scenario": scenario, "tool_to_call": "", "tool_args": {}, "tool_result": None}
    
    for event in graph.stream(initial_state, config):
        pass
        
    # --- PHASE 2: Resume (If Paused) ---
    # Check if the graph yielded an interrupt payload
    paused_state = graph.get_state(config)
    if paused_state.tasks and getattr(paused_state.tasks[0], "interrupts", None):
        print(f"  [API] Graph paused. Awaiting human input...")
        graph.invoke(Command(resume=human_payload), config)

# Run Scenarios
run_simulation("thread-1", "Safe Tool")
run_simulation("thread-2", "Approve Tool", {"action": "approve"})
run_simulation("thread-3", "Reject Tool", {"action": "reject"})
run_simulation("thread-4", "Edit Tool Arguments", {"action": "approve", "edited_recipient": "bob@example.com"})