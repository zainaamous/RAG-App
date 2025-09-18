import os
import time
import hashlib
from typing import List, Optional
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone
from pinecone.exceptions import NotFoundException
from langchain_core.documents import Document

# splits documents into chunks, embeds them, and upserts them into Pinecone
from config import (
    GOOGLE_API_KEY, PINECONE_API_KEY, INDEX_NAME, RAG_NAMESPACE,
    CHUNK_SIZE, CHUNK_OVERLAP, DOC_ID_HASH_MODE, USER_AGENT
)
from filesys import iter_files, load_one_local, doc_uid_for_path, doc_uid_for_content


# ---------- Helpers ----------
def build_chunk_ids(ns: str, doc_uid: str, n: int) -> List[str]:
    """Generate unique IDs for each chunk of a document in a namespace."""
    return [f"{ns}:{doc_uid}:{i:07d}" for i in range(n)]


def sentinel_id(ns: str, doc_uid: str) -> str:
    """Unique ID for the sentinel vector of a document."""
    return f"{ns}:{doc_uid}:SENTINEL"


def sentinel_exists(index, ns: str, doc_uid: str) -> bool:
    """Check if a sentinel vector already exists (doc already indexed)."""
    sid = sentinel_id(ns, doc_uid)
    got = index.fetch(ids=[sid], namespace=ns)  # returns {} if missing
    return bool(got and got.vectors and sid in got.vectors)


def upsert_sentinel(index, ns: str, embedder, doc_uid: str, source: str, chunk_count: int):
    """Insert a sentinel vector to mark that this doc was indexed."""
    vec = embedder.embed_query(f"sentinel:{doc_uid}")  # embedding of a dummy string
    index.upsert(
        vectors=[{
            "id": sentinel_id(ns, doc_uid),
            "values": vec,
            "metadata": {
                "kind": "sentinel",
                "doc_uid": doc_uid,
                "source": source,
                "chunk_count": chunk_count
            }
        }],
        namespace=ns
    )


def wait_for_namespace(index, ns: str, expected_min_increase: int, timeout: float = 20.0, interval: float = 1.0):
    """Wait until the namespace shows the expected increase in vector count."""
    stats0 = index.describe_index_stats()
    base = stats0.get("namespaces", {}).get(ns, {}).get("vectorCount", 0)
    deadline = time.time() + timeout
    last = base
    while time.time() < deadline:
        stats = index.describe_index_stats()
        cnt = stats.get("namespaces", {}).get(ns, {}).get("vectorCount", 0)
        last = cnt
        if cnt >= base + expected_min_increase:
            return True
        time.sleep(interval)
    print(f"[WARN] wait_for_namespace timed out. last={last}, expected_at_least={base + expected_min_increase}")
    return False


# ---------- Main indexing ----------
def index_paths(paths: List[str], namespace: str, wipe: bool = False, reindex: bool = False):
    """Index files into Pinecone under the given namespace."""
    try:
        files = iter_files(paths)
        if not files:
            print("[ERR] No supported files found.")
            return

        # Validate API keys
        if not PINECONE_API_KEY:
            raise ValueError("PINECONE_API_KEY is not set")
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is not set")

        # embeddings + Pinecone client
        embed = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index = pc.Index(INDEX_NAME)
        vs = PineconeVectorStore(embedding=embed, index=index)
        
    except Exception as e:
        print(f"[ERR] Failed to initialize indexing components: {e}")
        return

    # Optionally clear namespace
    if wipe:
        try:
            index.delete(namespace=namespace, delete_all=True)
            print(f"[CLEAN] Cleared namespace '{namespace}'")
        except NotFoundException:
            print(f"[CLEAN] Namespace '{namespace}' not found at delete time.")

    # Splitter
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        add_start_index=True,
        separators=["\n## ", "\n# ", "\n\n", "\n", " "]
    )

    total_new = 0
    for path in files:
        # Decide document UID
        doc_uid = doc_uid_for_path(path) if DOC_ID_HASH_MODE == "PATH" else doc_uid_for_content(path)

        if not reindex and sentinel_exists(index, namespace, doc_uid):
            print(f"[SKIP] Already indexed: {path}")
            continue

        if reindex:
            try:
                index.delete(namespace=namespace, filter={"doc_uid": doc_uid})
                index.delete(namespace=namespace, ids=[sentinel_id(namespace, doc_uid)])
                print(f"[REINDEX] Cleared previous vectors for doc_uid={doc_uid}")
            except Exception as e:
                print(f"[REINDEX WARN] {e}")

        try:
            # Load + split
            docs = load_one_local(path, USER_AGENT)
            if not docs:
                print(f"[WARN] No content loaded from {path}")
                continue
                
            chunks = splitter.split_documents(docs)
            if not chunks:
                print(f"[WARN] No chunks created from {path}")
                continue
                
            for d in chunks:
                d.metadata["source"] = path
                d.metadata["doc_uid"] = doc_uid
                d.metadata["chunk_start"] = d.metadata.get("start_index", 0)

            ids = build_chunk_ids(namespace, doc_uid, len(chunks))

            # Upsert chunks
            upserted = vs.add_documents(documents=chunks, ids=ids, namespace=namespace)
            print(f"[OK] {os.path.basename(path)} -> {len(upserted)} chunks")

            # Upsert sentinel
            upsert_sentinel(index, namespace, embed, doc_uid, path, len(upserted))
            total_new += (len(upserted) + 1)
            
        except Exception as e:
            print(f"[ERR] Failed to process {path}: {e}")
            continue

    if total_new:
        wait_for_namespace(index, namespace, expected_min_increase=total_new)


if __name__ == "__main__":
    import sys
    # Usage:
    #   python index_fs.py <path_or_glob_or_dir> [more paths...] [--wipe] [--reindex] [--ns=NAME]
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]

    if not args:
        print("Usage:\n  python index_fs.py <path|dir|glob> [more ...] [--wipe] [--reindex] [--ns=NAME]")
        sys.exit(1)

    ns = RAG_NAMESPACE
    wipe = "--wipe" in flags
    reindex = "--reindex" in flags
    for f in flags:
        if f.startswith("--ns="):
            ns = f.split("=", 1)[1]

    index_paths(args, namespace=ns, wipe=wipe, reindex=reindex)

import time, sys, subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

DOCS = r"RAG_pip2\docs"
NS = "library-global"

class Handler(FileSystemEventHandler):
    def on_any_event(self, event):
        if event.is_directory: return
        subprocess.run(
            ["python", "RAG_pip2\\index_fs.py", DOCS, "--ns="+NS],
            check=False
        )

if __name__ == "__main__":
    obs = Observer()
    obs.schedule(Handler(), DOCS, recursive=True)
    print(f"Watching {DOCS}; indexing to namespace '{NS}' on changes. Ctrl+C to stop.")
    obs.start()
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        obs.stop()
    obs.join()
