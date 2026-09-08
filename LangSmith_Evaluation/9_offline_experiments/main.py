import os
import time
from pathlib import Path

from dotenv import load_dotenv
from langsmith import Client
from langsmith.evaluation import evaluate

# ==========================================
# 1. Environment Configuration & Safety Check
# ==========================================
ENV_PATH = Path(r"F:\ai_agents_langgraph\Learn-AI-Agents\LangSmith_Evaluation\.env")
load_dotenv(dotenv_path=ENV_PATH)

API_KEY = os.getenv("LANGSMITH_API_KEY", "").strip()

if not API_KEY:
    print("\nERROR: LANGSMITH_API_KEY is empty in your .env file!")
    print("Please generate an API key at https://smith.langchain.com/settings/api-keys")
    print(f"and add it to: {ENV_PATH}")
    exit(1)

# Initialize the client now that we know we have a key
try:
    client = Client()
except Exception as e:
    print(f"\nERROR: Failed to initialize LangSmith Client. Check your API key. Details: {e}")
    exit(1)

# ==========================================
# 2. Dataset Initialization
# ==========================================
DATASET_NAME = "Agent-AB-Testing-Dataset"

def setup_dataset():
    print(f"[System] Verifying Dataset '{DATASET_NAME}'...")
    try:
        if client.has_dataset(dataset_name=DATASET_NAME):
            client.delete_dataset(dataset_name=DATASET_NAME)
            
        dataset = client.create_dataset(dataset_name=DATASET_NAME)
        client.create_examples(
            inputs=[
                {"question": "What is the capital of France?"},
                {"question": "How many days for a refund?"}
            ],
            outputs=[
                {"answer": "Paris"}, 
                {"answer": "14 days"}
            ],
            dataset_id=dataset.id
        )
        print("  -> Dataset created successfully.")
    except Exception as e:
        print(f"\nERROR: Failed to connect to LangSmith. Your API Key might be invalid: {e}")
        exit(1)

# ==========================================
# 3. Target A (V1 Baseline - Fast but Dumb)
# ==========================================
def agent_v1_baseline(inputs: dict) -> dict:
    """Simulates a small, fast model doing zero-shot generation."""
    time.sleep(0.1) # Fast latency
    question = inputs["question"]
    
    if "capital" in question.lower():
        return {"answer": "Paris"}
    return {"answer": "I don't know."}

# ==========================================
# 4. Target B (V2 Hybrid - Slow but Smart)
# ==========================================
def agent_v2_hybrid(inputs: dict) -> dict:
    """Simulates a heavy RAG pipeline with a massive model."""
    time.sleep(1.5) # Slow latency
    question = inputs["question"]
    
    if "capital" in question.lower():
        return {"answer": "The capital is Paris."}
    return {"answer": "You have 14 days."}

# ==========================================
# 5. Evaluators
# ==========================================
def exact_match_evaluator(run, example) -> dict:
    expected = example.outputs.get("answer", "").lower()
    predicted = run.outputs.get("answer", "").lower()
    return {"key": "exact_match", "score": 1 if expected == predicted else 0}

def semantic_contains_evaluator(run, example) -> dict:
    expected = example.outputs.get("answer", "").lower()
    predicted = run.outputs.get("answer", "").lower()
    return {"key": "semantic_contains", "score": 1 if expected in predicted else 0}

# ==========================================
# 6. Execute A/B Experiment
# ==========================================
if __name__ == "__main__":
    setup_dataset()
    
    print(f"\n{'='*60}\n[Running Experiment A: V1 Baseline]")
    evaluate(
        agent_v1_baseline,
        data=DATASET_NAME,
        evaluators=[exact_match_evaluator, semantic_contains_evaluator],
        experiment_prefix="V1-Baseline",
    )
    
    print(f"\n{'='*60}\n[Running Experiment B: V2 Hybrid]")
    evaluate(
        agent_v2_hybrid,
        data=DATASET_NAME,
        evaluators=[exact_match_evaluator, semantic_contains_evaluator],
        experiment_prefix="V2-Hybrid",
    )
    
    print("\n[System] Experiments completed!")
    print("Go to LangSmith -> 'Datasets & Testing' -> Click your dataset.")
    print("Click the 'Compare' button in the top right to view the A/B scorecard!")