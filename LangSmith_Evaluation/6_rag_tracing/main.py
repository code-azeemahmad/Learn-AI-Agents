import os
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_qdrant import QdrantVectorStore
from langgraph.graph import END, START, StateGraph
from langsmith import traceable

# ==========================================
# 1. Environment Configuration
# ==========================================

ENV_PATH = Path(
    r"F:\ai_agents_langgraph\Learn-AI-Agents\LangSmith_Evaluation\.env"
)

load_dotenv(dotenv_path=ENV_PATH)

QDRANT_URL = "http://localhost:6333/"
MODEL_NAME = os.getenv(
    "OLLAMA_MODEL_NAME",
    "gemma4:26b"
)


# ==========================================
# 2. Providers
# ==========================================

embeddings = OllamaEmbeddings(
    model="nomic-embed-text",
    base_url="http://localhost:11434/"
)

llm = ChatOllama(
    model=MODEL_NAME,
    base_url="http://localhost:11434/"
)


# ==========================================
# 3. Indexing Pipeline
# ==========================================

@traceable(
    name="Document_Indexing_Pipeline"
)
def index_documents():

    print("\n[Indexing] Upserting documents into Qdrant...")

    docs = [
        Document(
            page_content=(
                "Enterprise refund policy: "
                "All refunds must be processed within "
                "30 days of invoice."
            ),
            metadata={
                "tenant_id": "tenant_A"
            },
        ),
        Document(
            page_content=(
                "Vacation policy: "
                "Employees get 20 days of PTO."
            ),
            metadata={
                "tenant_id": "tenant_A"
            },
        ),
    ]

    QdrantVectorStore.from_documents(
        docs,
        embeddings,
        url=QDRANT_URL,
        prefer_grpc=False,
        collection_name="enterprise_knowledge",
        force_recreate=True,
    )
    
    print("  -> Indexing Complete.")

    return {
        "status": "success",
        "documents_indexed": len(docs),
    }



# ==========================================
# 4. RAG State
# ==========================================

class RagState(TypedDict):
    question: str
    rewritten_query: str
    context: str
    answer: str


# ==========================================
# 5. RAG Nodes
# ==========================================

def query_rewrite_node(state: RagState):

    print("  [RAG] Rewriting query...")

    messages = [
        SystemMessage(
            content=(
                "Extract the core search keywords "
                "from the user query. "
                "Output ONLY the keywords."
            )
        ),
        HumanMessage(
            content=state["question"]
        ),
    ]

    response = llm.invoke(messages)

    return {
        "rewritten_query": response.content.strip()
    }


def retrieve_node(state: RagState):

    print("  [RAG] Retrieving from Qdrant...")

    vector_store = (
        QdrantVectorStore.from_existing_collection(
            embedding=embeddings,
            collection_name="enterprise_knowledge",
            url=QDRANT_URL,
        )
    )

    docs = vector_store.similarity_search(
        state["rewritten_query"],
        k=1,
    )

    if docs:
        context = docs[0].page_content
    else:
        context = "No relevant documents found."

    return {
        "context": context
    }


def generate_node(state: RagState):

    print("  [RAG] Generating final answer...")

    messages = [
        SystemMessage(
            content=(
                "Answer the user strictly using this context:\n"
                f"{state['context']}"
            )
        ),
        HumanMessage(
            content=state["question"]
        ),
    ]

    response = llm.invoke(messages)

    return {
        "answer": response.content
    }


# ==========================================
# 6. Build Graph
# ==========================================

builder = StateGraph(RagState)

builder.add_node(
    "rewrite",
    query_rewrite_node
)

builder.add_node(
    "retrieve",
    retrieve_node
)

builder.add_node(
    "generate",
    generate_node
)

builder.add_edge(
    START,
    "rewrite"
)

builder.add_edge(
    "rewrite",
    "retrieve"
)

builder.add_edge(
    "retrieve",
    "generate"
)

builder.add_edge(
    "generate",
    END
)

rag_graph = builder.compile()


# ==========================================
# 7. Parent Application Trace
# ==========================================

@traceable(
    name="RAG_Application"
)
def run_rag_application(question: str):

    # Child trace #1
    index_documents()

    # Child trace #2
    result = rag_graph.invoke(
        {
            "question": question,
            "rewritten_query": "",
            "context": "",
            "answer": "",
        },
        config={
            "run_name": "rag_query_pipeline",
            "tags": [
                "rag",
                "v1"
            ],
            "metadata": {
                "tenant_id": "tenant_A"
            },
        },
    )

    return result


# ==========================================
# 8. Run
# ==========================================

if __name__ == "__main__":

    result = run_rag_application(
        "How long do I have to request a refund?"
    )

    print("\n[Final Answer]:")
    print(result["answer"])