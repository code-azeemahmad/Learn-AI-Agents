import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_qdrant import QdrantVectorStore
from langsmith import Client
from langsmith.evaluation import evaluate

# ==========================================
# 1. Environment Configuration
# ==========================================
ENV_PATH = Path(r"F:\ai_agents_langgraph\Learn-AI-Agents\LangSmith_Evaluation\.env")
load_dotenv(dotenv_path=ENV_PATH)

QDRANT_URL = "http://localhost:6333/"
MODEL_NAME = os.getenv("OLLAMA_MODEL_NAME", "gemma4:26b")

embeddings = OllamaEmbeddings(model="nomic-embed-text", base_url="http://localhost:11434/")
llm = ChatOllama(model=MODEL_NAME, base_url="http://localhost:11434/", temperature=0.0)
client = Client()

# ==========================================
# 2. Indexing Pipeline
# ==========================================
def setup_qdrant():
    print("[System] Indexing documents to Qdrant...")
    docs = [
        Document(page_content="Refund policy: All customer refunds must be requested within 14 days of purchase."),
        Document(page_content="Data access: Contractors cannot access payroll or HR documents."),
    ]
    QdrantVectorStore.from_documents(
        docs, embeddings, url=QDRANT_URL, collection_name="eval_knowledge", force_recreate=True
    )

# ==========================================
# 3. Target Application (RAG Pipeline)
# ==========================================
def rag_pipeline(inputs: dict) -> dict:
    """The target function we are evaluating. Takes Dataset inputs, returns outputs."""
    question = inputs["question"]
    
    vector_store = QdrantVectorStore.from_existing_collection(
        embedding=embeddings, collection_name="eval_knowledge", url=QDRANT_URL
    )
    
    docs = vector_store.similarity_search(question, k=1)
    context = docs[0].page_content if docs else "No context found."
    
    messages = [
        SystemMessage(content=f"Answer based ONLY on this context: {context}"),
        HumanMessage(content=question)
    ]
    
    response = llm.invoke(messages)
    return {"answer": response.content}

# ==========================================
# 4. Dataset Creation
# ==========================================
dataset_name = "Enterprise-RAG-Eval-V1"

def setup_dataset():
    if client.has_dataset(dataset_name=dataset_name):
        client.delete_dataset(dataset_name=dataset_name)
        
    dataset = client.create_dataset(dataset_name=dataset_name)
    client.create_examples(
        inputs=[
            {"question": "How long do I have to request a refund?"},
            {"question": "Can temporary contractors view HR files?"}
        ],
        outputs=[
            {"answer": "14 days"}, 
            {"answer": "No"}
        ],
        dataset_id=dataset.id
    )
    return dataset_name

# ==========================================
# 5. Evaluators
# ==========================================
def code_evaluator_not_empty(run, example) -> dict:
    """Deterministic Code Evaluator: Simply checks if the LLM returned a blank string."""
    predicted_answer = run.outputs.get("answer", "")
    score = 1 if len(predicted_answer.strip()) > 5 else 0
    return {"key": "is_not_empty", "score": score}

def llm_judge_correctness(run, example) -> dict:
    """Semantic LLM-as-a-Judge Evaluator: Uses an LLM to grade factual alignment."""
    expected = example.outputs.get("answer", "")
    predicted = run.outputs.get("answer", "")
    
    prompt = f"""
    You are an impartial judge. 
    Compare the Expected Answer to the Predicted Answer.
    Expected: {expected}
    Predicted: {predicted}
    
    If the Predicted answer conveys the same factual information as the Expected answer, reply with '1'. 
    Otherwise, reply with '0'. 
    Output ONLY the number.
    """
    
    judge_response = llm.invoke([HumanMessage(content=prompt)]).content.strip()
    
    # Parse the LLM's response into a float (fallback to 0 if it hallucinated text)
    try:
        score = float(judge_response)
    except ValueError:
        score = 0.0
        
    return {"key": "llm_semantic_correctness", "score": score}

# ==========================================
# 6. Execution: Run the Experiment!
# ==========================================
if __name__ == "__main__":
    setup_qdrant()
    setup_dataset()
    
    print(f"\n{'='*60}\n[Running LangSmith Evaluation Experiment]")
    
    # The `evaluate` function orchestrates the whole process:
    # It loops through the dataset, feeds inputs to the RAG pipeline, 
    # runs the evaluators on the output, and uploads the results to LangSmith!
    experiment_results = evaluate(
        rag_pipeline,
        data=dataset_name,
        evaluators=[code_evaluator_not_empty, llm_judge_correctness],
        experiment_prefix="RAG-Baseline-Test",
        metadata={"model": MODEL_NAME, "env": "local"}
    )
    
    print("\n[System] Experiment completed successfully!")
    print("Go to LangSmith -> 'Datasets & Testing' -> Click your dataset to see the scorecard!")