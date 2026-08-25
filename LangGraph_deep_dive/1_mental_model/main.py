from dataclasses import dataclass


@dataclass
class State:
    user_input: str
    result: str | None = None

# Tools
def search_tool(query: str) -> str:
    return f"Search result for: {query}"

def calculator_tool(expression: str) -> str:
    try:
        # Simple eval for demonstration (safe enough for this controlled script)
        return f"Calculation result: {eval(expression)}"
    except Exception as e:
        return f"Calculation error: {e}"

# The "Agent" (Manual Control Flow)
def simple_agent(state: State) -> State:
    query = state.user_input.lower()
    
    print(f"--- Processing: '{state.user_input}' ---")
    
    # DECISION + ACTION + STATE UPDATE
    if "search" in query:
        print("Decision: Route to Search")
        state.result = search_tool(state.user_input)
    elif "calculate" in query or any(op in query for op in ["+", "-", "*", "/"]):
        print("Decision: Route to Calculator")
        clean_expr = query.replace("calculate", "").strip()
        state.result = calculator_tool(clean_expr)
    else:
        print("Decision: Route to Direct Response")
        state.result = "I can answer directly."
        
    return state

# --- Testing the Architecture ---
print(simple_agent(State(user_input="Search for information about LangGraph")))
print(simple_agent(State(user_input="Calculate 10 * 5")))
print(simple_agent(State(user_input="What is your favorite color?")))