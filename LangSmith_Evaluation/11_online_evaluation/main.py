import os
import time
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama
from langsmith import Client
from pydantic import BaseModel, Field

# ==========================================
# 1. Environment & Initialization
# ==========================================
ENV_PATH = Path(r"F:\ai_agents_langgraph\Learn-AI-Agents\LangSmith_Evaluation\.env")
load_dotenv(dotenv_path=ENV_PATH)

MODEL_NAME = os.getenv("OLLAMA_MODEL_NAME", "gemma4:26b")
llm = ChatOllama(model=MODEL_NAME, base_url="http://localhost:11434/", temperature=0.0)

try:
    client = Client()
except Exception as e:
    print(f"\nERROR: Failed to initialize LangSmith Client: {e}")
    exit(1)

# ==========================================
# 2. Online Evaluator Schemas
# ==========================================
class JudgeScore(BaseModel):
    reasoning: str = Field(description="Step-by-step reasoning for the evaluation.")
    score: float = Field(description="1.0 for Pass/Yes, 0.0 for Fail/No.")

structured_judge = llm.with_structured_output(JudgeScore)

# ==========================================
# 3. Code Evaluators (Fast, Deterministic)
# ==========================================
def eval_answer_not_empty(run) -> tuple[float, str]:
    """Code Evaluator 1: Checks if the system returned a blank response."""
    outputs = run.outputs or {}
    answer = outputs.get("answer", str(outputs))
    
    if len(answer.strip()) > 0:
        return 1.0, "Answer contains text."
    return 0.0, "Answer is completely empty."

def eval_latency_ok(run) -> tuple[float, str]:
    """Code Evaluator 2: Checks if response time is under 5 seconds."""
    duration_seconds = (run.end_time - run.start_time).total_seconds()
    
    if duration_seconds < 5.0:
        return 1.0, f"Fast response: {duration_seconds:.2f}s"
    return 0.0, f"Slow response: {duration_seconds:.2f}s"

# ==========================================
# 4. LLM-as-a-Judge Evaluators (Reference-Free)
# ==========================================
def eval_answer_relevance(run) -> tuple[float, str]:
    """LLM Judge 1: Does the answer address the user's question? (No reference needed)"""
    user_input = run.inputs.get("question", str(run.inputs))
    outputs = run.outputs or {}
    ai_output = outputs.get("answer", str(outputs))
    
    prompt = f"""
    Evaluate this production interaction.
    User Query: "{user_input}"
    AI Response: "{ai_output}"
    
    Did the AI provide a relevant response that addresses the user's core query?
    """
    
    try:
        result = structured_judge.invoke([HumanMessage(content=prompt)])
        return result.score, result.reasoning
    except Exception as e:
        return 0.0, f"Judge failed: {e}"

def eval_groundedness(run) -> tuple[float, str]:
    """LLM Judge 2: Did the model hallucinate, or stick to the retrieved context?"""
    outputs = run.outputs or {}
    context = outputs.get("retrieved_context", "")
    ai_output = outputs.get("answer", str(outputs))
    
    if not context:
        return 0.0, "No context was retrieved to ground the answer."
        
    prompt = f"""
    Evaluate this production interaction for hallucinations.
    Retrieved Context: "{context}"
    AI Response: "{ai_output}"
    
    Is the AI Response strictly supported by the Retrieved Context, without adding outside facts?
    """
    
    try:
        result = structured_judge.invoke([HumanMessage(content=prompt)])
        return result.score, result.reasoning
    except Exception as e:
        return 0.0, f"Judge failed: {e}"

# ==========================================
# 5. The Production Monitoring Loop
# ==========================================
def run_production_monitor():
    print(f"\n{'='*60}\n[Starting Online Monitoring Simulator]")
    
    # --- Project Selection ---
    projects = list(client.list_projects())
    if not projects:
        print("No projects found! Run a standard LangGraph trace first.")
        return
        
    target_project = next((p for p in projects if p.name == "hello_smith"), None)
    if not target_project:
        target_project = next((p for p in projects if p.name == "default"), None)
    if not target_project:
        target_project = projects[0]
        
    print(f"Targeting Project: '{target_project.name}'")
    
    # --- Fetch Recent Traces ---
    try:
        recent_runs = list(client.runs.query(
            project_ids=[target_project.id], 
            is_root=True,
            has_error=False,
            limit=3  # Limit to 3 so it doesn't take too long locally
        ))
    except Exception as e:
        print(f"Failed to fetch runs: {e}")
        return

    if not recent_runs:
        print(f"  No recent successful traces found in '{target_project.name}'.")
        return
        
    print(f"  Found {len(recent_runs)} traces to evaluate.\n")
    
    # --- Evaluation Loop ---
    for run in recent_runs:
        print(f"🔍 Evaluating Trace: {run.id}")
        
        # 1. Answer Not Empty
        empty_score, empty_reason = eval_answer_not_empty(run)
        client.create_feedback(run.id, key="answer_not_empty", score=empty_score, comment=empty_reason)
        
        # 2. Latency
        latency_score, latency_reason = eval_latency_ok(run)
        client.create_feedback(run.id, key="latency_ok", score=latency_score, comment=latency_reason)
        
        # 3. Answer Relevance
        rel_score, rel_reason = eval_answer_relevance(run)
        client.create_feedback(run.id, key="online_relevance", score=rel_score, comment=rel_reason)
        
        # 4. Groundedness
        ground_score, ground_reason = eval_groundedness(run)
        client.create_feedback(run.id, key="online_groundedness", score=ground_score, comment=ground_reason)
        
        print(f"   [Code] Not Empty: {empty_score} | Latency: {latency_score}")
        print(f"   [LLM]  Relevance: {rel_score} | Groundedness: {ground_score}")
        print("   ---")
        
        time.sleep(1) # Be nice to local Ollama

    print("\n[System] Monitoring run complete. All feedback logged to LangSmith!")

if __name__ == "__main__":
    run_production_monitor()