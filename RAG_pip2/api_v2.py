"""
Enhanced API v2 for RAG System
Advanced features including streaming, batch operations, and real-time monitoring
"""
import os
import tempfile
import uuid
import asyncio
from typing import List, Optional, Dict, Any, AsyncGenerator
from datetime import datetime, timedelta
import json
from collections import defaultdict

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, validator
import re
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Import enhanced modules
from config import config, config_manager, ConfigManager
from logger import logger, log_operation, log_performance, log_error
from indexer import EnhancedIndexer, IndexingResult, IndexingStats
from query_engine import EnhancedQueryEngine, QueryResult, QueryType
from conversation_manager import conversation_manager, ConversationMessage, ConversationSummary
# Optional system monitoring
try:
    from system_monitor import system_monitor, check_pinecone_health, check_llm_health, check_database_health
    SYSTEM_MONITOR_AVAILABLE = True
except ImportError:
    SYSTEM_MONITOR_AVAILABLE = False
    # Create dummy functions
    def system_monitor():
        return None
    def check_pinecone_health():
        return True
    def check_llm_health():
        return True
    def check_database_health():
        return True

# Security
security = HTTPBearer(auto_error=False)

# Rate limiting
class RateLimiter:
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)
    
    def is_allowed(self, client_ip: str) -> bool:
        now = datetime.now()
        window_start = now - timedelta(seconds=self.window_seconds)
        
        # Clean old requests
        self.requests[client_ip] = [
            req_time for req_time in self.requests[client_ip] 
            if req_time > window_start
        ]
        
        # Check if under limit
        if len(self.requests[client_ip]) >= self.max_requests:
            return False
        
        # Add current request
        self.requests[client_ip].append(now)
        return True

rate_limiter = RateLimiter(max_requests=100, window_seconds=60)

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

# Request logging middleware with rate limiting
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = datetime.now()
        client_ip = request.client.host if request.client else "unknown"
        
        # Check rate limit
        if not rate_limiter.is_allowed(client_ip):
            return Response(
                content="Rate limit exceeded. Please try again later.",
                status_code=429,
                headers={"Retry-After": "60"}
            )
        
        # Log request
        log_operation("api_request", 
                     method=request.method,
                     url=str(request.url),
                     client_ip=client_ip)
        
        response = await call_next(request)
        
        # Log response and record metrics
        duration = (datetime.now() - start_time).total_seconds()
        is_error = response.status_code >= 400
        
        # Record request metrics
        if SYSTEM_MONITOR_AVAILABLE and system_monitor:
            system_monitor.record_request(duration, is_error)
        
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
    conversation_id: Optional[str] = None
    
    @validator('question')
    def validate_question(cls, v):
        if not v or not v.strip():
            raise ValueError('Question cannot be empty')
        if len(v) > 10000:
            raise ValueError('Question too long (max 10000 characters)')
        # Basic XSS protection
        if re.search(r'<script|javascript:|data:', v, re.IGNORECASE):
            raise ValueError('Question contains potentially harmful content')
        return v.strip()
    
    @validator('conversation_id')
    def validate_conversation_id(cls, v):
        if v and not re.match(r'^[a-f0-9-]{36}$', v):
            raise ValueError('Invalid conversation ID format')
        return v

class StreamingQueryRequest(BaseModel):
    question: str
    namespace: str = Field(default_factory=lambda: config.rag_namespace)
    chunk_size: int = Field(default=50, ge=10, le=200)
    conversation_id: Optional[str] = None

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
    conversation_id: Optional[str] = None

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

class ConversationRequest(BaseModel):
    title: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = {}

class ConversationResponse(BaseModel):
    conversation_id: str
    title: str
    created_at: str
    message_count: int

class ConversationHistoryResponse(BaseModel):
    conversation_id: str
    messages: List[Dict[str, Any]]
    summary: Optional[str] = None

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

# ...existing imports...
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
# Add your Pinecone and summarization imports here

router = APIRouter()



@app.get("/health", response_model=HealthResponse)
async def health_check(namespace: str = None):
    """Enhanced health check with system information"""
    namespace = namespace or config.rag_namespace
    
    try:
        # Use system monitor for comprehensive health check
        if SYSTEM_MONITOR_AVAILABLE and system_monitor:
            system_status = system_monitor.get_system_status()
            
            # Test all components using system monitor
            pinecone_health = system_monitor.check_component_health("pinecone", check_pinecone_health)
            llm_health = system_monitor.check_component_health("llm", check_llm_health)
            db_health = system_monitor.check_component_health("database", check_database_health)
        else:
            # Fallback without system monitor
            system_status = {"overall_status": "healthy", "uptime_seconds": 0}
            pinecone_health = type('obj', (object,), {'status': 'healthy'})()
            llm_health = type('obj', (object,), {'status': 'healthy'})()
            db_health = type('obj', (object,), {'status': 'healthy'})()
        
        # Get indexer stats
        try:
            indexer = EnhancedIndexer(namespace)
            stats = await asyncio.get_event_loop().run_in_executor(
                None, indexer.get_namespace_stats
            )
        except Exception as e:
            stats = {"vector_count": 0, "index_dimension": 0}
        
        system_info = {
            "version": "2.0.0",
            "config": {
                "chunk_size": config.chunking.chunk_size,
                "embedding_model": config.embedding.model,
                "llm_model": config.llm.model
            },
            "vector_count": stats.get("vector_count", 0),
            "index_dimension": stats.get("index_dimension", 0),
            "system_status": system_status,
            "component_health": {
                "pinecone": pinecone_health.status,
                "llm": llm_health.status,
                "database": db_health.status
            }
        }
        
        return HealthResponse(
            status=system_status["overall_status"],
            namespace=namespace,
            vector_count=stats.get("vector_count"),
            system_info=system_info,
            uptime=f"{system_status['uptime_seconds']:.0f}s"
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
            # Use conversation-aware query if conversation_id is provided
            if req.conversation_id:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, engine.answer_question, req.question, req.conversation_id
                )
            else:
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
            metadata=result.metadata,
            conversation_id=result.metadata.get("conversation_id")
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
        
        # Get system monitoring data
        if SYSTEM_MONITOR_AVAILABLE and system_monitor:
            system_status = system_monitor.get_system_status()
            performance_summary = system_monitor.get_performance_summary()
        else:
            system_status = {"overall_status": "healthy", "uptime_seconds": 0, "request_count": 0, "error_count": 0, "error_rate": 0}
            performance_summary = {"message": "System monitoring not available"}
        
        system_health = {
            "overall_status": system_status["overall_status"],
            "uptime_seconds": system_status["uptime_seconds"],
            "request_count": system_status["request_count"],
            "error_count": system_status["error_count"],
            "error_rate_percent": system_status["error_rate"],
            "performance": performance_summary,
            "latest_metrics": system_status["latest_metrics"]
        }
        
        return SystemStatsResponse(
            indexing_stats=indexing_stats,
            query_stats=query_stats,
            system_health=system_health
        )
        
    except Exception as e:
        log_error(e, "api_system_stats")
        raise HTTPException(status_code=500, detail=f"Failed to get system stats: {str(e)}")

@app.get("/metrics")
async def get_metrics(hours: int = 24):
    """Get system metrics history"""
    try:
        if SYSTEM_MONITOR_AVAILABLE and system_monitor:
            metrics_history = system_monitor.get_metrics_history(hours=hours)
            performance_summary = system_monitor.get_performance_summary()
        else:
            metrics_history = []
            performance_summary = {"message": "System monitoring not available"}
        
        return {
            "metrics_history": metrics_history,
            "performance_summary": performance_summary,
            "time_range_hours": hours
        }
        
    except Exception as e:
        log_error(e, "api_metrics")
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")

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

# ---- CONVERSATION MANAGEMENT ENDPOINTS ----

@app.post("/conversations", response_model=ConversationResponse)
async def create_conversation(req: ConversationRequest):
    """Create a new conversation"""
    try:
        conversation_id = conversation_manager.create_conversation(
            title=req.title, 
            metadata=req.metadata
        )
        
        return ConversationResponse(
            conversation_id=conversation_id,
            title=req.title or f"Conversation {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            created_at=datetime.now().isoformat(),
            message_count=0
        )
        
    except Exception as e:
        log_error(e, "api_create_conversation")
        raise HTTPException(status_code=500, detail=f"Failed to create conversation: {str(e)}")

@app.get("/conversations", response_model=List[ConversationResponse])
async def list_conversations(limit: int = 50):
    """List recent conversations"""
    try:
        conversations = conversation_manager.list_conversations(limit=limit)
        
        return [
            ConversationResponse(
                conversation_id=conv["conversation_id"],
                title=conv["title"],
                created_at=conv["created_at"],
                message_count=conv["message_count"]
            )
            for conv in conversations
        ]
        
    except Exception as e:
        log_error(e, "api_list_conversations")
        raise HTTPException(status_code=500, detail=f"Failed to list conversations: {str(e)}")

@app.get("/conversations/{conversation_id}", response_model=ConversationHistoryResponse)
async def get_conversation_history(conversation_id: str, limit: int = 50):
    """Get conversation history"""
    try:
        messages = conversation_manager.load_conversation_history(conversation_id, limit=limit)
        
        # Get conversation summary if available
        summary_obj = conversation_manager.get_conversation_summary(conversation_id)
        summary_text = summary_obj.summary_text if summary_obj else None
        
        return ConversationHistoryResponse(
            conversation_id=conversation_id,
            messages=[
                {
                    "message_id": msg.message_id,
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                    "metadata": msg.metadata
                }
                for msg in messages
            ],
            summary=summary_text
        )
        
    except Exception as e:
        log_error(e, "api_get_conversation_history", conversation_id=conversation_id)
        raise HTTPException(status_code=500, detail=f"Failed to get conversation history: {str(e)}")

@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation"""
    try:
        success = conversation_manager.delete_conversation(conversation_id)
        
        if success:
            return {"status": "deleted", "conversation_id": conversation_id}
        else:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(e, "api_delete_conversation", conversation_id=conversation_id)
        raise HTTPException(status_code=500, detail=f"Failed to delete conversation: {str(e)}")

@app.post("/conversations/{conversation_id}/summarize")
async def summarize_conversation(conversation_id: str):
    """Manually trigger conversation summarization"""
    try:
        # Check if conversation exists
        history = conversation_manager.load_conversation_history(conversation_id, limit=1)
        if not history:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Create query engine to generate summary
        engine = EnhancedQueryEngine(config.rag_namespace)
        engine._create_conversation_summary(conversation_id)
        
        return {"status": "summarized", "conversation_id": conversation_id}
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(e, "api_summarize_conversation", conversation_id=conversation_id)
        raise HTTPException(status_code=500, detail=f"Failed to summarize conversation: {str(e)}")

@app.post("/conversations/cleanup")
async def cleanup_old_conversations(days_old: int = 30):
    """Clean up old conversations"""
    try:
        deleted_count = conversation_manager.cleanup_old_conversations(days_old=days_old)
        
        return {
            "status": "cleaned_up",
            "deleted_count": deleted_count,
            "days_old": days_old
        }
        
    except Exception as e:
        log_error(e, "api_cleanup_conversations")
        raise HTTPException(status_code=500, detail=f"Failed to cleanup conversations: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
