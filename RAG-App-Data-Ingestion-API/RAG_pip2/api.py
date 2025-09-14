# api.py
import os
import tempfile
import uuid
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.documents import Document

# Import your existing modules
from index_fs import index_paths, sentinel_exists, sentinel_id
from query import build_pipeline
from config import RAG_NAMESPACE, PINECONE_API_KEY, INDEX_NAME
from filesys import doc_uid_for_content, load_one_local, USER_AGENT
from pinecone import Pinecone

app = FastAPI(
    title="RAG Knowledge Base API",
    description="API for ingesting documents and querying the RAG knowledge base",
    version="1.0.0"
)

# Add CORS middleware for web applications
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- MODELS ----
class IngestRequest(BaseModel):
    doc_id: Optional[str] = None
    namespace: str = RAG_NAMESPACE
    content: str
    tags: Optional[List[str]] = []
    source: Optional[str] = None  # Custom source identifier

class QueryRequest(BaseModel):
    question: str
    namespace: str = RAG_NAMESPACE
    max_docs: int = 3
    k_per_doc: int = 6

class DocumentResponse(BaseModel):
    doc_id: str
    namespace: str
    source: str
    chunk_count: Optional[int] = None
    status: str

class QueryResponse(BaseModel):
    answer: str
    sources: List[str]
    namespace: str

class HealthResponse(BaseModel):
    status: str
    namespace: str
    vector_count: Optional[int] = None

# ---- HELPER FUNCTIONS ----
def get_pinecone_index():
    """Get Pinecone index instance"""
    pc = Pinecone(api_key=PINECONE_API_KEY)
    return pc.Index(INDEX_NAME)

def create_temp_document(content: str, doc_id: str = None) -> str:
    """Create a temporary document file and return its path"""
    if not doc_id:
        doc_id = str(uuid.uuid4())
    
    # Create temp file with .txt extension
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write(content)
        return f.name

# ---- ENDPOINTS ----

@app.get("/health", response_model=HealthResponse)
def health_check(namespace: str = RAG_NAMESPACE):
    """Check API health and get namespace statistics"""
    try:
        index = get_pinecone_index()
        stats = index.describe_index_stats()
        vector_count = stats.get("namespaces", {}).get(namespace, {}).get("vectorCount", 0)
        return HealthResponse(
            status="healthy",
            namespace=namespace,
            vector_count=vector_count
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@app.post("/ingest", response_model=DocumentResponse)
def ingest_doc(req: IngestRequest):
    """Ingest a document into the knowledge base"""
    try:
        # Create temporary file
        temp_path = create_temp_document(req.content, req.doc_id)
        
        # Generate document UID using your existing system
        doc_uid = doc_uid_for_content(temp_path)
        
        # Check if already indexed (unless reindexing)
        index = get_pinecone_index()
        if sentinel_exists(index, req.namespace, doc_uid):
            # Clean up temp file
            os.unlink(temp_path)
            return DocumentResponse(
                doc_id=doc_uid,
                namespace=req.namespace,
                source=req.source or temp_path,
                status="already_indexed"
            )
        
        # Index the document using your existing system
        index_paths([temp_path], namespace=req.namespace, reindex=False)
        
        # Clean up temp file
        os.unlink(temp_path)
        
        # Get chunk count from sentinel
        sentinel_data = index.fetch(ids=[sentinel_id(req.namespace, doc_uid)], namespace=req.namespace)
        chunk_count = None
        if sentinel_data.vectors:
            chunk_count = sentinel_data.vectors[sentinel_id(req.namespace, doc_uid)].metadata.get("chunk_count")
        
        return DocumentResponse(
            doc_id=doc_uid,
            namespace=req.namespace,
            source=req.source or "api_upload",
            chunk_count=chunk_count,
            status="indexed"
        )
        
    except Exception as e:
        # Clean up temp file if it exists
        if 'temp_path' in locals():
            try:
                os.unlink(temp_path)
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

@app.post("/ingest/file")
def ingest_file(
    file: UploadFile = File(...),
    namespace: str = Form(default=RAG_NAMESPACE),
    doc_id: Optional[str] = Form(default=None),
    source: Optional[str] = Form(default=None)
):
    """Upload and ingest a file into the knowledge base"""
    try:
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as temp_file:
            content = file.file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        # Generate document UID
        doc_uid = doc_uid_for_content(temp_path)
        
        # Check if already indexed
        index = get_pinecone_index()
        if sentinel_exists(index, namespace, doc_uid):
            os.unlink(temp_path)
            return {"status": "already_indexed", "doc_id": doc_uid}
        
        # Index the file
        index_paths([temp_path], namespace=namespace, reindex=False)
        
        # Clean up
        os.unlink(temp_path)
        
        return {"status": "indexed", "doc_id": doc_uid, "filename": file.filename}
        
    except Exception as e:
        if 'temp_path' in locals():
            try:
                os.unlink(temp_path)
            except:
                pass
        raise HTTPException(status_code=500, detail=f"File ingestion failed: {str(e)}")

@app.post("/query", response_model=QueryResponse)
def query_doc(req: QueryRequest):
    """Query the knowledge base"""
    try:
        # Build pipeline with custom parameters
        retrieve, generate = build_pipeline(
            namespace=req.namespace,
            max_docs=req.max_docs,
            k_per_doc=req.k_per_doc
        )
        
        # Process query
        state = {"question": req.question, "context": [], "answer": ""}
        s = state | retrieve(state)
        out = generate(s)
        
        # Extract sources
        sources = [d.metadata.get("source", "unknown") for d in s["context"]]
        
        return QueryResponse(
            answer=out["answer"],
            sources=sources,
            namespace=req.namespace
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

@app.get("/documents/{doc_id}")
def get_document_info(doc_id: str, namespace: str = RAG_NAMESPACE):
    """Get information about a specific document"""
    try:
        index = get_pinecone_index()
        sentinel_data = index.fetch(ids=[sentinel_id(namespace, doc_id)], namespace=namespace)
        
        if not sentinel_data.vectors:
            raise HTTPException(status_code=404, detail="Document not found")
        
        vector_data = sentinel_data.vectors[sentinel_id(namespace, doc_id)]
        metadata = vector_data.metadata
        
        return {
            "doc_id": doc_id,
            "namespace": namespace,
            "source": metadata.get("source"),
            "chunk_count": metadata.get("chunk_count"),
            "indexed_at": metadata.get("timestamp")  # You might want to add this
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get document info: {str(e)}")

@app.delete("/documents/{doc_id}")
def delete_doc(doc_id: str, namespace: str = RAG_NAMESPACE):
    """Delete a document from the knowledge base"""
    try:
        index = get_pinecone_index()
        
        # Delete all chunks for this document
        index.delete(
            namespace=namespace,
            filter={"doc_uid": doc_id}
        )
        
        # Delete sentinel
        index.delete(
            namespace=namespace,
            ids=[sentinel_id(namespace, doc_id)]
        )
        
        return {"status": "deleted", "doc_id": doc_id, "namespace": namespace}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")

@app.get("/documents", response_model=List[Dict[str, Any]])
def list_documents(namespace: str = RAG_NAMESPACE, limit: int = 100):
    """List documents in the namespace"""
    try:
        index = get_pinecone_index()
        
        # Query for sentinel vectors (documents)
        query_response = index.query(
            namespace=namespace,
            vector=[0.0] * 768,  # Dummy vector for metadata query
            filter={"kind": "sentinel"},
            top_k=limit,
            include_metadata=True
        )
        
        documents = []
        for match in query_response.matches:
            metadata = match.metadata
            documents.append({
                "doc_id": metadata.get("doc_uid"),
                "source": metadata.get("source"),
                "chunk_count": metadata.get("chunk_count"),
                "score": match.score
            })
        
        return documents
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")

@app.post("/reindex/{doc_id}")
def reindex_doc(doc_id: str, namespace: str = RAG_NAMESPACE):
    """Reindex a specific document"""
    try:
        # This would require storing the original content
        # For now, we'll just delete and ask user to re-upload
        raise HTTPException(
            status_code=501, 
            detail="Reindexing requires original content. Please delete and re-upload the document."
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reindexing failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
