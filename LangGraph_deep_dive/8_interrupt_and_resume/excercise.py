from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict


class State(TypedDict):
    text_input: str
    human_answer: str

def ask_human(state: State):
    answer = interrupt("Do you approve?")
    return {
        "human_answer": answer
    }

builder = StateGraph(State)
builder.add_node("ask_human", ask_human)
builder.add_edge(START, "ask_human")
builder.add_edge("ask_human", END)

graph = builder.compile(checkpointer=InMemorySaver())

config = {"configurable": {"thread_id": "test-thread"}}

pause_state = graph.invoke(
    {
        "input_text": "Hello", 
        "human_answer": "",
    }, 
    config=config
)

final_state = graph.invoke(
    Command(resume="I approve!"),
    config=config
)

print(final_state)