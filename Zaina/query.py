from typing import TypedDict, List
from collections import defaultdict
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

def build_pipeline(namespace: str, max_docs: int = 10, k_per_doc: int = 20, pool_k: int = 200, pool_fetch_k: int = 300):
    llm = init_chat_model("gemini-2.5-flash", model_provider="google_genai")
    embed = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index(INDEX_NAME)
    vs = PineconeVectorStore(embedding=embed, index=index)
    prompt = hub.pull("rlm/rag-prompt")

    def retrieve(state: State):
        hits = vs.similarity_search_with_score(
            state["question"],
            k=pool_k,
            namespace=namespace,
            search_type="mmr",
            fetch_k=pool_fetch_k
        )
        by_doc = defaultdict(list)
        for doc, score in hits:
            by_doc[doc.metadata.get("doc_uid")].append((doc, score))

        ranked_docs = sorted(by_doc.items(), key=lambda kv: min(s for _, s in kv[1]))[:max_docs]

        chosen = []
        for _, grp in ranked_docs:
            top_chunks = sorted(grp, key=lambda x: x[1])[:k_per_doc]
            chosen.extend(doc for doc, _ in top_chunks)

        print("\nTop hits (single-doc context):")
        for i, d in enumerate(chosen, 1):
            print(f" #{i} source={d.metadata.get('source')} start={d.metadata.get('chunk_start')}")
            print("  ", d.page_content[:160].replace("\n"," "), "...")
        return {"context": chosen}

    def generate(state: State):
        docs_content = "\n\n".join(doc.page_content for doc in state["context"])
        messages = prompt.invoke({"question": state["question"], "context": docs_content})
        resp = llm.invoke(messages)
        return {"answer": resp.content}

    return retrieve, generate


if __name__ == "__main__":
    import sys
    ns = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else RAG_NAMESPACE

    retrieve, generate = build_pipeline(ns)
    print(f"Namespace: {ns}. Type 'exit' to quit.")

    while True:
        try:
            q = input("\nQ> ").strip()
            if not q:
                continue
            if q.lower() in {"exit", "quit", "q"}:
                break

            state = {"question": q, "context": [], "answer": ""}
            s = state | retrieve(state)
            out = generate(s)
            print("\nA>", out["answer"])
        except (KeyboardInterrupt, EOFError):
            break