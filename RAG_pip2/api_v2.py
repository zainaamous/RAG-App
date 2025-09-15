"""
Enhanced API v2 for RAG System
Advanced features including streaming, batch operations, and real-time monitoring
"""
import os
import tempfile
import uuid
import asyncio
from typing import List, Optional, Dict, Any, AsyncGenerator
from datetime import datetime
import json

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Import enhanced modules
from config import config, config_manager, ConfigManager
from logger import logger, log_operation, log_performance, log_error
from indexer import EnhancedIndexer, IndexingResult, IndexingStats
from query_engine import EnhancedQueryEngine, QueryResult, QueryType

# Security
security = HTTPBearer(auto_error=False)

app = FastAPI(
    title="Enhanced RAG Knowledge Base API v2",
    description="Advanced API for document ingestion, querying, and management",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = datetime.now()
        
        # Log request
        log_operation("api_request", 
                     method=request.method,
                     url=str(request.url),
                     client_ip=request.client.host)
        
        response = await call_next(request)
        
        # Log response
        duration = (datetime.now() - start_time).total_seconds()
        log_performance("api_request", duration,
                       status_code=response.status_code,
                       method=request.method)
        
        return response

app.add_middleware(RequestLoggingMiddleware)

# ---- ENHANCED MODELS ----
class IngestRequest(BaseModel):
    doc_id: Optional[str] = None
    namespace: str = Field(default_factory=lambda: config.rag_namespace)
    content: str
    tags: Optional[List[str]] = []
    source: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = {}

class BatchIngestRequest(BaseModel):
    documents: List[IngestRequest]
    namespace: str = Field(default_factory=lambda: config.rag_namespace)
    options: Optional[Dict[str, Any]] = {}

class QueryRequest(BaseModel):
    question: str
    namespace: str = Field(default_factory=lambda: config.rag_namespace)
    max_docs: int = Field(default=3, ge=1, le=10)
    k_per_doc: int = Field(default=6, ge=1, le=20)
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    stream: bool = False

class StreamingQueryRequest(BaseModel):
    question: str
    namespace: str = Field(default_factory=lambda: config.rag_namespace)
    chunk_size: int = Field(default=50, ge=10, le=200)

class DocumentResponse(BaseModel):
    doc_id: str
    namespace: str
    source: str
    chunk_count: Optional[int] = None
    status: str
    processing_time: float
    metadata: Optional[Dict[str, Any]] = {}

class EnhancedQueryResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    namespace: str
    query_type: str
    confidence: float
    processing_time: float
    total_chunks_retrieved: int
    relevant_chunks_used: int
    metadata: Dict[str, Any]

class HealthResponse(BaseModel):
    status: str
    namespace: str
    vector_count: Optional[int] = None
    system_info: Dict[str, Any]
    uptime: str

class SystemStatsResponse(BaseModel):
    indexing_stats: Dict[str, Any]
    query_stats: Dict[str, Any]
    system_health: Dict[str, Any]

# ---- WEBSOCKET CONNECTIONS ----
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket connection established", total_connections=len(self.active_connections))
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info("WebSocket connection closed", total_connections=len(self.active_connections))
    
    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except:
                disconnected.append(connection)
        
        # Clean up disconnected connections
        for connection in disconnected:
            self.disconnect(connection)

manager = ConnectionManager()

# ---- UTILITY FUNCTIONS ----
def create_temp_document(content: str, doc_id: str = None) -> str:
    """Create temporary document file"""
    if not doc_id:
        doc_id = str(uuid.uuid4())
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write(content)
        return f.name

async def cleanup_temp_file(file_path: str):
    """Clean up temporary file"""
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
    except Exception as e:
        logger.warning("Failed to cleanup temp file", file_path=file_path, error=str(e))

# ---- ENHANCED ENDPOINTS ----

@app.get("/health", response_model=HealthResponse)
async def health_check(namespace: str = None):
    """Enhanced health check with system information"""
    namespace = namespace or config.rag_namespace
    
    try:
        indexer = EnhancedIndexer(namespace)
        stats = await asyncio.get_event_loop().run_in_executor(
            None, indexer.get_namespace_stats
        )
        
        system_info = {
            "version": "2.0.0",
            "config": {
                "chunk_size": config.chunking.chunk_size,
                "embedding_model": config.embedding.model,
                "llm_model": config.llm.model
            },
            "vector_count": stats.get("vector_count", 0),
            "index_dimension": stats.get("index_dimension", 0)
        }
        
        return HealthResponse(
            status="healthy",
            namespace=namespace,
            vector_count=stats.get("vector_count"),
            system_info=system_info,
            uptime="N/A"  # Could implement uptime tracking
        )
        
    except Exception as e:
        log_error(e, "health_check")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@app.post("/ingest", response_model=DocumentResponse)
async def ingest_doc(req: IngestRequest, background_tasks: BackgroundTasks):
    """Enhanced document ingestion with better error handling"""
    temp_path = None
    
    try:
        log_operation("api_ingest", doc_id=req.doc_id, namespace=req.namespace)
        
        # Create temporary file
        temp_path = create_temp_document(req.content, req.doc_id)
        
        # Index document
        indexer = EnhancedIndexer(req.namespace)
        result = await asyncio.get_event_loop().run_in_executor(
            None, indexer._index_single_document, temp_path, False
        )
        
        if not result.success:
            raise HTTPException(status_code=400, detail=f"Ingestion failed: {result.error}")
        
        # Schedule cleanup
        background_tasks.add_task(cleanup_temp_file, temp_path)
        
        # Broadcast to WebSocket clients
        await manager.broadcast({
            "type": "document_ingested",
            "data": {
                "doc_id": result.doc_id,
                "namespace": req.namespace,
                "chunks_created": result.chunks_created
            }
        })
        
        return DocumentResponse(
            doc_id=result.doc_id,
            namespace=req.namespace,
            source=req.source or "api_upload",
            chunk_count=result.chunks_created,
            status="indexed",
            processing_time=result.duration,
            metadata={"version": "2.0"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(e, "api_ingest")
        if temp_path:
            background_tasks.add_task(cleanup_temp_file, temp_path)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

@app.post("/ingest/batch")
async def batch_ingest(req: BatchIngestRequest, background_tasks: BackgroundTasks):
    """Batch document ingestion"""
    try:
        log_operation("api_batch_ingest", 
                     doc_count=len(req.documents), 
                     namespace=req.namespace)
        
        indexer = EnhancedIndexer(req.namespace)
        results = []
        
        # Process documents in parallel
        tasks = []
        for doc_req in req.documents:
            task = asyncio.create_task(
                _process_single_ingest(doc_req, indexer, background_tasks)
            )
            tasks.append(task)
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        successful = []
        failed = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed.append({
                    "index": i,
                    "error": str(result)
                })
            elif isinstance(result, dict) and result.get("success"):
                successful.append(result)
            else:
                failed.append({
                    "index": i,
                    "error": "Unknown error"
                })
        
        # Broadcast batch completion
        await manager.broadcast({
            "type": "batch_ingest_complete",
            "data": {
                "total": len(req.documents),
                "successful": len(successful),
                "failed": len(failed)
            }
        })
        
        return {
            "total": len(req.documents),
            "successful": len(successful),
            "failed": len(failed),
            "results": successful,
            "errors": failed
        }
        
    except Exception as e:
        log_error(e, "api_batch_ingest")
        raise HTTPException(status_code=500, detail=f"Batch ingestion failed: {str(e)}")

async def _process_single_ingest(doc_req: IngestRequest, indexer: EnhancedIndexer, 
                               background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """Process a single document ingestion"""
    temp_path = None
    
    try:
        temp_path = create_temp_document(doc_req.content, doc_req.doc_id)
        result = await asyncio.get_event_loop().run_in_executor(
            None, indexer._index_single_document, temp_path, False
        )
        
        background_tasks.add_task(cleanup_temp_file, temp_path)
        
        return {
            "success": result.success,
            "doc_id": result.doc_id,
            "chunks_created": result.chunks_created,
            "processing_time": result.duration,
            "error": result.error
        }
        
    except Exception as e:
        if temp_path:
            background_tasks.add_task(cleanup_temp_file, temp_path)
        raise e

@app.post("/ingest/file")
async def ingest_file(
    file: UploadFile = File(...),
    namespace: str = Form(default=None),
    doc_id: Optional[str] = Form(default=None),
    source: Optional[str] = Form(default=None),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Enhanced file upload with metadata"""
    temp_path = None
    
    try:
        namespace = namespace or config.rag_namespace
        
        log_operation("api_file_upload", 
                     filename=file.filename, 
                     namespace=namespace)
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        # Index file
        indexer = EnhancedIndexer(namespace)
        result = await asyncio.get_event_loop().run_in_executor(
            None, indexer._index_single_document, temp_path, False
        )
        
        if not result.success:
            raise HTTPException(status_code=400, detail=f"File ingestion failed: {result.error}")
        
        # Schedule cleanup
        background_tasks.add_task(cleanup_temp_file, temp_path)
        
        return {
            "status": "indexed",
            "doc_id": result.doc_id,
            "filename": file.filename,
            "chunks_created": result.chunks_created,
            "processing_time": result.duration,
            "namespace": namespace
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(e, "api_file_upload")
        if temp_path:
            background_tasks.add_task(cleanup_temp_file, temp_path)
        raise HTTPException(status_code=500, detail=f"File ingestion failed: {str(e)}")

@app.post("/query", response_model=EnhancedQueryResponse)
async def query_doc(req: QueryRequest):
    """Enhanced query with detailed response"""
    try:
        log_operation("api_query", 
                     question=req.question[:100], 
                     namespace=req.namespace)
        
        # Create query engine with custom parameters
        engine = EnhancedQueryEngine(req.namespace)
        
        # Temporarily update config for this query
        original_max_docs = config.retrieval.max_docs
        original_k_per_doc = config.retrieval.k_per_doc
        original_threshold = config.retrieval.similarity_threshold
        
        config.retrieval.max_docs = req.max_docs
        config.retrieval.k_per_doc = req.k_per_doc
        config.retrieval.similarity_threshold = req.similarity_threshold
        
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, engine.query, req.question
            )
        finally:
            # Restore original config
            config.retrieval.max_docs = original_max_docs
            config.retrieval.k_per_doc = original_k_per_doc
            config.retrieval.similarity_threshold = original_threshold
        
        return EnhancedQueryResponse(
            answer=result.answer,
            sources=result.sources,
            namespace=req.namespace,
            query_type=result.query_type.value,
            confidence=result.confidence,
            processing_time=result.processing_time,
            total_chunks_retrieved=result.total_chunks_retrieved,
            relevant_chunks_used=result.relevant_chunks_used,
            metadata=result.metadata
        )
        
    except Exception as e:
        log_error(e, "api_query")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

@app.post("/query/stream")
async def stream_query(req: StreamingQueryRequest):
    """Stream query response for real-time chat"""
    
    async def generate_response():
        try:
            engine = EnhancedQueryEngine(req.namespace)
            
            # Send initial response
            yield f"data: {json.dumps({'type': 'start', 'message': 'Processing query...'})}\n\n"
            
            # Process query
            result = await asyncio.get_event_loop().run_in_executor(
                None, engine.query, req.question
            )
            
            # Send answer in chunks
            answer = result.answer
            for i in range(0, len(answer), req.chunk_size):
                chunk = answer[i:i + req.chunk_size]
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                await asyncio.sleep(0.1)  # Small delay for streaming effect
            
            # Send metadata
            yield f"data: {json.dumps({'type': 'metadata', 'data': {'confidence': result.confidence, 'sources': len(result.sources)}})}\n\n"
            
            # Send sources
            yield f"data: {json.dumps({'type': 'sources', 'data': result.sources})}\n\n"
            
            # Send completion
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_response(),
        media_type="text/plain",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)
    
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/documents", response_model=List[Dict[str, Any]])
async def list_documents(namespace: str = None, limit: int = 100):
    """Enhanced document listing"""
    namespace = namespace or config.rag_namespace
    
    try:
        indexer = EnhancedIndexer(namespace)
        documents = await asyncio.get_event_loop().run_in_executor(
            None, indexer.list_documents, limit
        )
        
        return documents
        
    except Exception as e:
        log_error(e, "api_list_documents")
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")

@app.get("/documents/{doc_id}")
async def get_document_info(doc_id: str, namespace: str = None):
    """Get detailed document information"""
    namespace = namespace or config.rag_namespace
    
    try:
        indexer = EnhancedIndexer(namespace)
        
        # Get namespace stats to verify document exists
        stats = await asyncio.get_event_loop().run_in_executor(
            None, indexer.get_namespace_stats
        )
        
        # In a real implementation, you'd query for specific document metadata
        return {
            "doc_id": doc_id,
            "namespace": namespace,
            "exists": True,  # Simplified - would need actual lookup
            "stats": stats
        }
        
    except Exception as e:
        log_error(e, "api_get_document_info")
        raise HTTPException(status_code=500, detail=f"Failed to get document info: {str(e)}")

@app.delete("/documents/{doc_id}")
async def delete_doc(doc_id: str, namespace: str = None):
    """Delete document with confirmation"""
    namespace = namespace or config.rag_namespace
    
    try:
        log_operation("api_delete_document", doc_id=doc_id, namespace=namespace)
        
        indexer = EnhancedIndexer(namespace)
        await asyncio.get_event_loop().run_in_executor(
            None, indexer._delete_document, doc_id
        )
        
        # Broadcast deletion
        await manager.broadcast({
            "type": "document_deleted",
            "data": {
                "doc_id": doc_id,
                "namespace": namespace
            }
        })
        
        return {"status": "deleted", "doc_id": doc_id, "namespace": namespace}
        
    except Exception as e:
        log_error(e, "api_delete_document")
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")

@app.get("/stats", response_model=SystemStatsResponse)
async def get_system_stats(namespace: str = None):
    """Get comprehensive system statistics"""
    namespace = namespace or config.rag_namespace
    
    try:
        indexer = EnhancedIndexer(namespace)
        query_engine = EnhancedQueryEngine(namespace)
        
        indexing_stats = await asyncio.get_event_loop().run_in_executor(
            None, indexer.get_namespace_stats
        )
        query_stats = await asyncio.get_event_loop().run_in_executor(
            None, query_engine.get_query_stats
        )
        
        system_health = {
            "api_status": "healthy",
            "database_status": "connected",
            "memory_usage": "N/A",  # Could implement actual memory monitoring
            "uptime": "N/A"
        }
        
        return SystemStatsResponse(
            indexing_stats=indexing_stats,
            query_stats=query_stats,
            system_health=system_health
        )
        
    except Exception as e:
        log_error(e, "api_system_stats")
        raise HTTPException(status_code=500, detail=f"Failed to get system stats: {str(e)}")

@app.post("/config/reload")
async def reload_config():
    """Reload configuration without restart"""
    try:
        global config_manager
        config_manager = ConfigManager()
        
        return {"status": "reloaded", "message": "Configuration reloaded successfully"}
        
    except Exception as e:
        log_error(e, "api_reload_config")
        raise HTTPException(status_code=500, detail=f"Config reload failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
