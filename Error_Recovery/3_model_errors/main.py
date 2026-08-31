from enum import Enum
from typing import Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

# ==========================================
# 1. State & Constants
# ==========================================
MAX_RETRIES = 2
MAX_REPAIRS = 2

class ModelErrorType(str, Enum):
    TIMEOUT = "timeout"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    CONTEXT_LIMIT = "context_limit"
    INVALID_OUTPUT = "invalid_output"
    AUTHENTICATION = "authentication"
    UNKNOWN = "unknown"

class AgentState(TypedDict):
    scenario: str
    prompt: str
    result: Optional[str]
    error_type: Optional[ModelErrorType]
    error_message: Optional[str]
    retry_count: int
    repair_count: int
    fallback_count: int
    next_action: Optional[Literal["retry", "repair", "fallback", "abort", "finish"]]

# ==========================================
# 2. Simulated Model Service
# ==========================================
def call_model_node(state: AgentState):
    """Simulates an LLM API call that fails in specific ways based on the scenario."""
    retries = state.get("retry_count", 0)
    repairs = state.get("repair_count", 0)
    print(f"\n  [Primary LLM] Calling Model... (Retries: {retries}, Repairs: {repairs})")
    
    if state["scenario"] == "Timeout Scenario":
        if retries < 1:
            print("    -> LLM Timeout occurred.")
            return {"error_type": ModelErrorType.TIMEOUT, "error_message": "Provider timed out after 30s."}
        print("    -> Success on retry!")
        return {"result": "Successfully generated answer.", "error_type": None}
        
    elif state["scenario"] == "Context Overflow":
        if repairs < 1:
            print(f"    -> HTTP 400: Context length exceeded. (Prompt length: {len(state['prompt'])} chars)")
            return {"error_type": ModelErrorType.CONTEXT_LIMIT, "error_message": "Prompt exceeds 8k tokens."}
        print(f"    -> Success! Prompt accepted. (Prompt length: {len(state['prompt'])} chars)")
        return {"result": "Answer generated from reduced context.", "error_type": None}
        
    elif state["scenario"] == "Provider Outage":
        print("    -> HTTP 503: Primary Provider is down.")
        return {"error_type": ModelErrorType.PROVIDER_UNAVAILABLE, "error_message": "OpenAI API is currently unavailable."}
        
    elif state["scenario"] == "Invalid Output":
        if repairs < 1:
            print("    -> Model output did not match Pydantic schema.")
            return {"error_type": ModelErrorType.INVALID_OUTPUT, "error_message": "Missing required field 'action'."}
        print("    -> Success! Model corrected the JSON schema.")
        return {"result": '{"action": "search"}', "error_type": None}

    return {"result": "Immediate Success!", "error_type": None}

# ==========================================
# 3. Recovery & Helper Nodes
# ==========================================
def classifier_node(state: AgentState):
    """Deterministically decides the recovery strategy based on the explicit error type."""
    error_type = state["error_type"]
    
    if not error_type:
        return {"next_action": "finish"}
        
    print(f"  [Classifier] Analyzing Model Error: {error_type}")
    
    if error_type == ModelErrorType.TIMEOUT:
        if state["retry_count"] >= MAX_RETRIES:
            return {"next_action": "fallback"}
        return {"next_action": "retry", "retry_count": state["retry_count"] + 1}
        
    elif error_type in {ModelErrorType.CONTEXT_LIMIT, ModelErrorType.INVALID_OUTPUT}:
        if state["repair_count"] >= MAX_REPAIRS:
            return {"next_action": "abort"}
        return {"next_action": "repair", "repair_count": state["repair_count"] + 1}
        
    elif error_type == ModelErrorType.PROVIDER_UNAVAILABLE:
        return {"next_action": "fallback"}
        
    elif error_type == ModelErrorType.AUTHENTICATION:
        return {"next_action": "abort"}

    return {"next_action": "abort"}

def repair_context_node(state: AgentState):
    """Mutates the state to fix the underlying issue before retrying."""
    print(f"  [Repair Node] Attempting to fix '{state['error_type']}'...")
    
    if state["error_type"] == ModelErrorType.CONTEXT_LIMIT:
        print("    -> Truncating old conversation history from the prompt...")
        # Simulate halving the context
        new_prompt = state["prompt"][:len(state["prompt"]) // 2]
        return {"prompt": new_prompt}
        
    elif state["error_type"] == ModelErrorType.INVALID_OUTPUT:
        print(f"    -> Appending validation error to prompt: {state['error_message']}")
        new_prompt = state["prompt"] + f"\n[SYSTEM]: Your last response failed validation: {state['error_message']}. Try again."
        return {"prompt": new_prompt}
        
    return {}

def fallback_model_node(state: AgentState):
    """Executes a secondary LLM provider when the primary fails."""
    print("  [Fallback LLM] Primary failed. Calling secondary provider (e.g., Gemini/Ollama)...")
    return {"result": "Success via Fallback Model.", "error_type": None}

def handle_result_node(state: AgentState):
    print(f"  [Output] Final Result: {state['result']}")
    return {}

# ==========================================
# 4. Routing Logic
# ==========================================
def recovery_router(state: AgentState) -> Literal["retry_llm", "repair_context", "fallback_llm", "handle_result", "__end__"]:
    action = state["next_action"]
    
    if action == "retry":
        print("  [Router] Retrying Primary LLM...")
        return "retry_llm"
    elif action == "repair":
        print("  [Router] Routing to Repair Node...")
        return "repair_context"
    elif action == "fallback":
        print("  [Router] Routing to Fallback Provider...")
        return "fallback_llm"
    elif action == "finish":
        return "handle_result"
        
    print("  [Router] Fatal Error. Aborting workflow.")
    return "__end__"

# ==========================================
# 5. Build Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("call_model", call_model_node)
builder.add_node("classifier", classifier_node)
builder.add_node("repair_context", repair_context_node)
builder.add_node("fallback_model", fallback_model_node)
builder.add_node("handle_result", handle_result_node)

builder.add_edge(START, "call_model")
builder.add_edge("call_model", "classifier")

builder.add_conditional_edges("classifier", recovery_router, {
    "retry_llm": "call_model",
    "repair_context": "repair_context",
    "fallback_llm": "fallback_model",
    "handle_result": "handle_result",
    "__end__": END
})

# Repair node loops back to the primary model
builder.add_edge("repair_context", "call_model")
builder.add_edge("fallback_model", "handle_result")
builder.add_edge("handle_result", END)

graph = builder.compile()

# ==========================================
# 6. Execution Scenarios
# ==========================================
def run_scenario(scenario: str):
    print(f"\n\n{'='*60}\n=== SCENARIO: {scenario.upper()} ===\n{'='*60}")
    # Initialize with a massive fake prompt
    graph.invoke({
        "scenario": scenario, "prompt": "A" * 15000, "result": None,
        "error_type": None, "error_message": None, 
        "retry_count": 0, "repair_count": 0, "fallback_count": 0, "next_action": None
    })

run_scenario("Timeout Scenario")
run_scenario("Context Overflow")
run_scenario("Invalid Output")
run_scenario("Provider Outage")