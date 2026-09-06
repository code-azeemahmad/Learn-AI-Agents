import re
from typing import Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph


# ==========================================
# 1. State Schema
# ==========================================
class AgentState(TypedDict):
    scenario: str
    
    # The pipeline state
    user_input: str
    sanitized_input: Optional[str]
    
    llm_response: Optional[str]
    sanitized_response: Optional[str]
    
    proposed_tool: Optional[str]
    proposed_args: Optional[dict]
    
    final_output: str

# ==========================================
# 2. Guardrail Nodes
# ==========================================
def before_model_guardrail(state: AgentState):
    """
    Deterministic Guardrail: Scans the user input for PII (SSN format) 
    and redacts it BEFORE the LLM sees it.
    """
    print(f"\n{'='*60}\n[Scenario]: {state['scenario']}")
    print("  [Guardrail 1: Before-Model] Scanning input for PII...")
    
    raw_input = state["user_input"]
    
    # Simple Regex for a Social Security Number (XXX-XX-XXXX)
    ssn_pattern = r"\b\d{3}-\d{2}-\d{4}\b"
    
    if re.search(ssn_pattern, raw_input):
        print("    -> PII DETECTED! Redacting SSN from prompt.")
        sanitized = re.sub(ssn_pattern, "[REDACTED_SSN]", raw_input)
        return {"sanitized_input": sanitized}
        
    print("    -> Input is clean.")
    return {"sanitized_input": raw_input}


def llm_node(state: AgentState):
    """Simulates the LLM."""
    print(f"  [LLM] Processing input: '{state.get('sanitized_input', '')}'")
    
    if state["scenario"] == "LLM Leaks Secret":
        return {"llm_response": "The master database password is 'hunter2'."}
        
    if state["scenario"] == "High-Risk Tool Call":
        return {"proposed_tool": "refund_order", "proposed_args": {"amount": 5000}}
        
    return {"llm_response": "I have processed your request safely."}


def after_model_guardrail(state: AgentState):
    """
    Deterministic Guardrail: Scans the LLM's output for known secrets 
    BEFORE sending it to the user.
    """
    response = state.get("llm_response")
    if not response:
        return {} # No text response, maybe a tool call.
        
    print("  [Guardrail 2: After-Model] Scanning LLM output for secrets...")
    
    if "hunter2" in response:
        print("    -> SECRETS DETECTED! Blocking output to prevent data leak.")
        return {"sanitized_response": "Error: Response blocked by Data Loss Prevention policy."}
        
    print("    -> Output is clean.")
    return {"sanitized_response": response}


def before_tool_guardrail(state: AgentState):
    """
    Business Policy Guardrail: Evaluates tool calls against strict rules.
    """
    tool = state.get("proposed_tool")
    if not tool:
        return {}
        
    args = state.get("proposed_args", {})
    print(f"  [Guardrail 3: Before-Tool] Evaluating Policy for {tool}({args})...")
    
    if tool == "refund_order":
        if args.get("amount", 0) > 1000:
            print("    -> POLICY TRIGGERED: Refunds > $1000 require Human Approval (HITL).")
            return {"final_output": "Execution Paused: Awaiting Manager Approval."}
            
    return {"final_output": f"Executing: {tool}()"}

# ==========================================
# 3. Routing Edges
# ==========================================
def route_after_llm(state: AgentState) -> Literal["after_model_guardrail", "before_tool_guardrail"]:
    """Routes based on whether the LLM outputted text or a tool call."""
    if state.get("proposed_tool"):
        return "before_tool_guardrail"
    return "after_model_guardrail"

def finalize_response(state: AgentState) -> dict:
    # Helper to map the final state
    if state.get("sanitized_response"):
        return {"final_output": state["sanitized_response"]}
    return {}

# ==========================================
# 4. Build Graph (FIXED NODE NAMES)
# ==========================================
builder = StateGraph(AgentState)

# We name the nodes exactly what the router returns
builder.add_node("before_model_guardrail", before_model_guardrail)
builder.add_node("llm", llm_node)
builder.add_node("after_model_guardrail", after_model_guardrail)
builder.add_node("before_tool_guardrail", before_tool_guardrail)
builder.add_node("finalize", finalize_response)

builder.add_edge(START, "before_model_guardrail")
builder.add_edge("before_model_guardrail", "llm")

# The conditional edge now correctly matches the node names!
builder.add_conditional_edges("llm", route_after_llm)

builder.add_edge("after_model_guardrail", "finalize")
builder.add_edge("before_tool_guardrail", END)
builder.add_edge("finalize", END)

graph = builder.compile()

# ==========================================
# 5. Execution Scenarios
# ==========================================
def run(scenario: str, input_text: str):
    final_state = graph.invoke({
        "scenario": scenario, 
        "user_input": input_text,
        "sanitized_input": None,
        "llm_response": None,
        "sanitized_response": None,
        "proposed_tool": None,
        "proposed_args": None,
        "final_output": ""
    })
    print(f"  [System Output]: {final_state.get('final_output', '')}")

# 1. PII Redaction
run("PII Redaction", "My social security number is 123-45-6789.")

# 2. DLP (Data Loss Prevention)
run("LLM Leaks Secret", "What is the password?")

# 3. Policy Enforcement
run("High-Risk Tool Call", "Refund me $5000 right now.")