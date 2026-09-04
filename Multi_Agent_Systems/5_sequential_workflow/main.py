from typing import Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph


# ==========================================
# 1. State Schema
# ==========================================
# In a sequential workflow, the state acts as the communication bus between stages.
class AgentState(TypedDict):
    scenario: str
    user_request: str
    
    # Each stage writes to its own explicit key
    validation_status: Optional[str]
    sql_result: Optional[str]
    analysis_result: Optional[str]
    final_report: Optional[str]

# ==========================================
# 2. Sequential Nodes
# ==========================================
def validate_request_node(state: AgentState) -> dict:
    """Stage 1: Pure Deterministic Python Logic (No LLM)"""
    print(f"\n{'='*60}\n[Scenario]: {state['scenario']}")
    print("  [Stage 1: Validation] Checking request structure...")
    
    if "finance" not in state["user_request"].lower():
        print("    -> Validation Failed: Missing required 'finance' keyword.")
        return {"validation_status": "failed"}
        
    print("    -> Validation Passed.")
    return {"validation_status": "passed"}

def sql_agent_node(state: AgentState) -> dict:
    """Stage 2: Tool-Using Agent (Simulated)"""
    print("  [Stage 2: SQL Agent] Booting... Converting request to SQL query.")
    
    if state["scenario"] == "Database Failure":
        print("    -> Database Timeout Exception!")
        return {"sql_result": "ERROR: Database Timeout"}
        
    print("    -> Query successful. Retrieved 500 rows.")
    return {"sql_result": "{'total_revenue': 1200000, 'expenses': 850000}"}

def analysis_agent_node(state: AgentState) -> dict:
    """Stage 3: LLM Reasoning Node"""
    print("  [Stage 3: Analysis Agent] Booting... Analyzing SQL metrics.")
    print(f"    -> Analyzing context: {state['sql_result']}")
    
    # We simulate the LLM analyzing the data
    analysis = "Revenue exceeded expenses by $350k. Profit margins look healthy."
    print(f"    -> Analysis complete: '{analysis}'")
    return {"analysis_result": analysis}

def writer_agent_node(state: AgentState) -> dict:
    """Stage 4: LLM Generation Node"""
    print("  [Stage 4: Writer Agent] Booting... Drafting final executive report.")
    
    report = f"EXECUTIVE SUMMARY:\n{state['analysis_result']}\nEND REPORT."
    print("    -> Report generated.")
    return {"final_report": report}

def error_handler_node(state: AgentState) -> dict:
    """Fallback node for sequence failures."""
    print("  [Error Handler] The pipeline encountered a fatal error. Generating fallback response.")
    return {"final_report": "The system encountered an error while generating the report. Please try again later."}

# ==========================================
# 3. Routing Edges
# ==========================================
def check_validation(state: AgentState) -> Literal["sql_agent_node", "error_handler_node"]:
    if state.get("validation_status") == "passed":
        return "sql_agent_node"
    return "error_handler_node"

def check_sql(state: AgentState) -> Literal["analysis_agent_node", "error_handler_node"]:
    sql_result = state.get("sql_result", "")
    if "ERROR" in sql_result:
        return "error_handler_node"
    return "analysis_agent_node"

# ==========================================
# 4. Build Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("validate_request_node", validate_request_node)
builder.add_node("sql_agent_node", sql_agent_node)
builder.add_node("analysis_agent_node", analysis_agent_node)
builder.add_node("writer_agent_node", writer_agent_node)
builder.add_node("error_handler_node", error_handler_node)

builder.add_edge(START, "validate_request_node")

# Sequential conditional logic (If success, go to next. If fail, go to error handler)
builder.add_conditional_edges("validate_request_node", check_validation)
builder.add_conditional_edges("sql_agent_node", check_sql)

# Fixed Sequential Logic
builder.add_edge("analysis_agent_node", "writer_agent_node")

builder.add_edge("writer_agent_node", END)
builder.add_edge("error_handler_node", END)

graph = builder.compile()

# ==========================================
# 5. Execution Scenarios
# ==========================================
def run(scenario: str, request: str):
    initial_state = {
        "scenario": scenario, "user_request": request, 
        "validation_status": None, "sql_result": None, 
        "analysis_result": None, "final_report": None
    }
    graph.invoke(initial_state)

run("Happy Path", "Prepare a monthly finance report.")
run("Validation Failure", "Prepare a monthly marketing report.")
run("Database Failure", "Prepare a monthly finance report.")