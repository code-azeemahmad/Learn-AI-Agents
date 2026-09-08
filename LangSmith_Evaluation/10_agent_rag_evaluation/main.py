import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_qdrant import QdrantVectorStore
from langsmith import Client, traceable
from langsmith.evaluation import evaluate
from pydantic import BaseModel, Field

# ==========================================
# 1. Environment & Initialization
# ==========================================
ENV_PATH = Path(r"F:\ai_agents_langgraph\Learn-AI-Agents\LangSmith_Evaluation\.env")
load_dotenv(dotenv_path=ENV_PATH)

QDRANT_URL = "http://localhost:6333/"
MODEL_NAME = os.getenv("OLLAMA_MODEL_NAME", "gemma4:26b")

embeddings = OllamaEmbeddings(model="nomic-embed-text", base_url="http://localhost:11434/")
# We use temperature=0.0 for deterministic evaluation
llm = ChatOllama(model=MODEL_NAME, base_url="http://localhost:11434/", temperature=0.0)
client = Client()

DATASET_NAME = "Enterprise-Copilot-RAG-Eval"

# ==========================================
# 2. Pydantic Schema for LLM Judges
# ==========================================
class JudgeScore(BaseModel):
    reasoning: str = Field(description="Step-by-step explanation of why this score was given.")
    score: float = Field(description="A strict float of 1.0 (Pass/Yes) or 0.0 (Fail/No).")

# Bind the schema to the LLM so it always returns valid JSON
structured_judge_llm = llm.with_structured_output(JudgeScore)

# ==========================================
# 3. Indexing & Dataset Prep
# ==========================================
def setup_environment():
    print("[System] Indexing documents...")
    docs = [
        Document(page_content="Policy A: Employee expenses must be submitted within 14 days."),
        Document(page_content="Policy B: Customer refunds take 30 days to process.")
    ]
    QdrantVectorStore.from_documents(
        docs, embeddings, url=QDRANT_URL, collection_name="eval_rag", force_recreate=True
    )
    
    if client.has_dataset(dataset_name=DATASET_NAME):
        client.delete_dataset(dataset_name=DATASET_NAME)
        
    dataset = client.create_dataset(dataset_name=DATASET_NAME)
    client.create_examples(
        inputs=[
            {"question": "What is the employee expense deadline?"},
            {"question": "How long do customer refunds take?"}
        ],
        outputs=[
            {"reference": "14 days for employees."}, 
            {"reference": "30 days for customers."}
        ],
        dataset_id=dataset.id
    )

# ==========================================
# 4. Target Application
# ==========================================
# NOTE: No @traceable decorator here. `evaluate()` automatically traces the target function.
def rag_target(inputs: dict) -> dict:
    """Returns the answer AND the retrieved documents for deep evaluation."""
    question = inputs.get("question", "")
    vector_store = QdrantVectorStore.from_existing_collection(
        embedding=embeddings, collection_name="eval_rag", url=QDRANT_URL
    )
    
    docs = vector_store.similarity_search(question, k=1)
    context = docs[0].page_content if docs else ""
    
    response = llm.invoke([
        SystemMessage(content=f"Answer using ONLY this context: {context}"),
        HumanMessage(content=question)
    ])
    
    return {
        "answer": response.content,
        "retrieved_context": context
    }

# ==========================================
# 5. Multi-Dimensional Evaluators
# ==========================================
def get_safe_outputs(run) -> dict:
    """Helper to safely extract outputs, preventing double-nesting KeyErrors."""
    outputs = run.outputs or {}
    if "answer" not in outputs and "output" in outputs and isinstance(outputs["output"], dict):
        return outputs["output"]
    return outputs

@traceable(name="Eval_Retrieval_Relevance")
def eval_retrieval_relevance(run, example) -> dict:
    outputs = get_safe_outputs(run)
    question = example.inputs.get("question", "")
    context = outputs.get("retrieved_context", "")
    
    if not context:
        return {"key": "retrieval_relevance", "score": 0.0, "comment": "No context retrieved."}
    
    prompt = f"Is this context: '{context}' highly relevant to answering this question: '{question}'?"
    
    try:
        judge_output = structured_judge_llm.invoke([HumanMessage(content=prompt)])
        return {"key": "retrieval_relevance", "score": judge_output.score, "comment": judge_output.reasoning}
    except Exception as e:
        return {"key": "retrieval_relevance", "score": 0.0, "comment": f"Parsing Error: {e}"}

@traceable(name="Eval_Faithfulness")
def eval_faithfulness(run, example) -> dict:
    outputs = get_safe_outputs(run)
    context = outputs.get("retrieved_context", "")
    answer = outputs.get("answer", "")
    
    if not answer:
        return {"key": "faithfulness", "score": 0.0, "comment": "No answer generated."}
    
    prompt = f"Can this answer: '{answer}' be completely deduced from this context: '{context}' without introducing outside information?"
    
    try:
        judge_output = structured_judge_llm.invoke([HumanMessage(content=prompt)])
        return {"key": "faithfulness", "score": judge_output.score, "comment": judge_output.reasoning}
    except Exception as e:
        return {"key": "faithfulness", "score": 0.0, "comment": f"Parsing Error: {e}"}

@traceable(name="Eval_Correctness")
def eval_correctness(run, example) -> dict:
    outputs = get_safe_outputs(run)
    reference = example.outputs.get("reference", "")
    answer = outputs.get("answer", "")
    
    if not answer:
        return {"key": "correctness", "score": 0.0, "comment": "No answer generated."}
    
    prompt = f"Are these two statements factually equivalent regarding their core claims?\n1. {reference}\n2. {answer}"
    
    try:
        judge_output = structured_judge_llm.invoke([HumanMessage(content=prompt)])
        return {"key": "correctness", "score": judge_output.score, "comment": judge_output.reasoning}
    except Exception as e:
        return {"key": "correctness", "score": 0.0, "comment": f"Parsing Error: {e}"}

# ==========================================
# 6. Execution
# ==========================================
if __name__ == "__main__":
    setup_environment()
    print(f"\n{'='*60}\n[Running Multi-Dimensional RAG Evaluation]")
    
    evaluate(
        rag_target,
        data=DATASET_NAME,
        evaluators=[eval_retrieval_relevance, eval_faithfulness, eval_correctness],
        experiment_prefix="RAG-Diagnostic-V2"
    )
    
    print("\n[System] Evaluation complete.")
    print("1. Check 'Datasets & Testing' to see your scorecard and the LLM's reasoning comments.")
    print("2. Check the 'Tracing' tab in your default project to see the internal execution of the Evaluators!")