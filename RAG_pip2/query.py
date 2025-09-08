from typing import TypedDict, List
from langchain.chat_models import init_chat_model
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain import hub
from pinecone import Pinecone
from langchain_core.documents import Document

from config import GOOGLE_API_KEY, PINECONE_API_KEY, INDEX_NAME, RAG_NAMESPACE

class State(TypedDict):
    question: str
    context: List[Document]
    answer: str

def build_pipeline(namespace: str):
    llm = init_chat_model("gemini-2.5-flash", model_provider="google_genai")
    embed = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index(INDEX_NAME)
    vs = PineconeVectorStore(embedding=embed, index=index)
    prompt = hub.pull("rlm/rag-prompt")

    def retrieve(state: State):
        hits = vs.similarity_search(
            state["question"], k=6, namespace=namespace,
            search_type="mmr", fetch_k=40
        )
        print("\nTop hits:")
        for i, doc in enumerate(hits, 1):
            print(f" #{i} source={doc.metadata.get('source')} start={doc.metadata.get('chunk_start')}")
            print("  ", doc.page_content[:160].replace("\n"," "), "...")
        return {"context": hits}

    def generate(state: State):
        docs_content = "\n\n".join(doc.page_content for doc in state["context"])
        messages = prompt.invoke({"question": state["question"], "context": docs_content})
        resp = llm.invoke(messages)
        return {"answer": resp.content}

    return retrieve, generate


if __name__ == "__main__":
    import sys
    ns = sys.argv[1] if len(sys.argv) > 2 and not sys.argv[1].startswith("--") else RAG_NAMESPACE
    question = sys.argv[2] if len(sys.argv) > 2 else "What skills does he have? Did he work with C language?"

    retrieve, generate = build_pipeline(ns)
    state = {"question": question, "context": [], "answer": ""}
    s = state | retrieve(state)  # add context
    out = generate(s)
    print("\n=== ANSWER ===\n", out["answer"])
