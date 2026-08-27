from typing import Annotated, Literal

from langchain_core.messages import AnyMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


# ==========================================
# 1. Define Tools
# ==========================================
@tool
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b

@tool
def multiply(a: int, b: int) -> int:
    """Multiply two integers."""
    return a * b

tools = [add, multiply]
tools_by_name = {t.name: t for t in tools}

# Bind tools to the LLM so it knows they exist
llm = ChatOllama(model="gemma4:26b", temperature=0)
llm_with_tools = llm.bind_tools(tools)

# ==========================================
# 2. State Schema
# ==========================================
class AgentState(TypedDict):
    # add_messages ensures new messages append rather than overwrite
    messages: Annotated[list[AnyMessage], add_messages]
    llm_calls: int

# ==========================================
# 3. Nodes
# ==========================================
def call_model(state: AgentState):
    print("  [Node: LLM] Thinking...")
    # The LLM reads the entire conversation history and generates the next message
    response = llm_with_tools.invoke(state["messages"])
    
    current_calls = state.get("llm_calls", 0)
    
    # We return the NEW message (it gets appended) and the UPDATED call count
    return {"messages": [response], "llm_calls": current_calls + 1}

def tool_node(state: AgentState):
    print("  [Node: Tool] Executing requested tools...")
    last_message = state["messages"][-1]
    
    tool_results = []
    
    # The LLM can request multiple tools at once, so we loop
    for tool_call in last_message.tool_calls:
        print(f"    -> Running {tool_call['name']} with args: {tool_call['args']}")
        tool_func = tools_by_name[tool_call["name"]]
        
        # Execute the Python function
        result = tool_func.invoke(tool_call["args"])
        
        # Package the result into a ToolMessage so the LLM can read it
        tool_results.append(
            ToolMessage(
                content=str(result),
                name=tool_call["name"],
                tool_call_id=tool_call["id"]
            )
        )
        
    return {"messages": tool_results}

# ==========================================
# 4. Conditional Router
# ==========================================
def should_continue(state: AgentState) -> Literal["tool_node", END]:
    # Safety Check: Infinite Loop Prevention
    if state.get("llm_calls", 0) >= 5:
        print("  [Router] Max LLM calls (5) reached. Forcing END.")
        return END
        
    last_message = state["messages"][-1]
    
    # Logic Check: Did the LLM request tools?
    if last_message.tool_calls:
        print("  [Router] LLM requested tools. Routing to Tool Node.")
        return "tool_node"
        
    print("  [Router] LLM provided final answer. Routing to END.")
    return END

# ==========================================
# 5. Build, Wire, & Compile the Graph
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("llm_call", call_model)
builder.add_node("tool_node", tool_node)

builder.add_edge(START, "llm_call")

builder.add_conditional_edges(
    "llm_call",
    should_continue,
    {"tool_node": "tool_node", END: END}
)

# The Agent Loop: After tools finish, route back to the LLM
builder.add_edge("tool_node", "llm_call")

checkpointer = InMemorySaver()
agent = builder.compile(checkpointer=checkpointer)

# ==========================================
# 6. Execution Tests
# ==========================================

def run_test(test_name: str, query: str, thread_id: str):
    print(f"\n=== {test_name}: '{query}' ===")
    config = {"configurable": {"thread_id": thread_id}}
    input_state = {
        "messages": [HumanMessage(content=query)],
        "llm_calls": 0
    }
    
    result = agent.invoke(input_state, config)
    final_message = result["messages"][-1].content
    print(f"\nFinal AI Answer: {final_message}")

# --- Run the tests ---
run_test("Test 1", "Add 3 and 4", "thread-1")
run_test("Test 2", "Multiply 6 and 7", "thread-2")
run_test("Test 3", "Hello!", "thread-3")

# Optional: Draw the architecture (if inside Jupyter or saving to file)
# agent.get_graph().draw_mermaid_png(output_file_path="agent_graph.png")