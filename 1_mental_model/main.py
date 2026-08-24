from dataclasses import dataclass


@dataclass
class State:    # state
    user_input: str
    result: str | None = None


def search_tool(query: str) -> str: # tool
    return f"Search result for: {query}"

def simple_agent(state: State) -> State:
    query = state.user_input.lower() 
    if "search" in query:   # decision
        state.result = search_tool(state.user_input)    # state update
    else:
        state.result = "I can answer directly."

    return state


state = State(
    user_input="Search for information about LangGraph"
)

state = simple_agent(state)
print(state)


"""
                    AI APPLICATION
                          │
          ┌───────────────┼────────────────┐
          │               │                │
          ▼               ▼                ▼
   Deterministic     Stateful          Agent
    Workflow         Workflow
          │               │                │
          │               │                │
       fixed          controlled       model-driven
        flow             flow             flow
                          │                │
                          └──────┬─────────┘
                                 ↓
                           LangGraph
                              Runtime
                                 ↓
                     State + Execution +
                     Persistence + Control
"""
# Who controls what happens next?
"""
Application
    ↓
Deterministic workflow

Application + state
    ↓
Stateful workflow

Model + application constraints
    ↓
Agent
"""