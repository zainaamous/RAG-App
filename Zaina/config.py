import os, getpass
from dotenv import load_dotenv

#Environment and configuration handeling (API Keys, Chunk sizes, mode flags)

#load_dotenv()
load_dotenv()

def env(name: str, prompt: str | None = None, default: str | None = None):
    val = os.environ.get(name)
    if not val and prompt:
        val = getpass.getpass(prompt)
        os.environ[name] = val
    return val or default
#What is Pipecone?
#Pinecone is a vector database that allows you to store and query vectors.
#Pinecone stores high-dimensional vectors (numerical representations of data).
#these vectors usually come from machine learning models that convert text, images, or audio into numerical representations (embeddings).
#Pinecone is mainly used for similarity search and semantic search.
#Pinecone is built for fast, scalable, real-time vector search, even with millions or billions of vectors.
GOOGLE_API_KEY = env("GOOGLE_API_KEY",  "Enter API key for Google Gemini: ")
PINECONE_API_KEY = env("PINECONE_API_KEY","Enter Pinecone API key: ")
INDEX_NAME = env("PINECONE_INDEX",  default="mahmoud")
USER_AGENT = os.environ.setdefault("USER_AGENT", "rag-local/1.0 (+you@example.com)")
RAG_NAMESPACE = env("RAG_NAMESPACE",   default="library-global")

CHUNK_SIZE = int(env("CHUNK_SIZE",   default="1000"))
CHUNK_OVERLAP = int(env("CHUNK_OVERLAP",default="200"))
DOC_ID_HASH_MODE = env("DOC_ID_HASH_MODE", default="PATH").upper()
