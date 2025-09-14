"""
Enhanced RAG Dashboard Server
Serves the web dashboard with real-time updates
"""
import os
import json
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.middleware.cors import CORSMiddleware

from config import config
from logger import logger
from indexer import EnhancedIndexer
from query_engine import EnhancedQueryEngine

# Create FastAPI app
app = FastAPI(
    title="Enhanced RAG Dashboard",
    description="Web dashboard for RAG system monitoring and management",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup static files and templates
dashboard_dir = Path(__file__).parent / "dashboard"
static_dir = dashboard_dir / "static"
templates_dir = dashboard_dir / "templates"

if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

if templates_dir.exists():
    templates = Jinja2Templates(directory=str(templates_dir))
else:
    templates = None

# Global instances
indexer = None
query_engine = None

@app.on_event("startup")
async def startup_event():
    """Initialize dashboard components"""
    global indexer, query_engine
    
    try:
        logger.info("Initializing dashboard components")
        
        indexer = EnhancedIndexer(config.rag_namespace)
        query_engine = EnhancedQueryEngine(config.rag_namespace)
        
        logger.info("Dashboard components initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize dashboard components: {e}")
        raise

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Serve the main dashboard page"""
    if not templates:
        raise HTTPException(status_code=500, detail="Dashboard templates not found")
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "title": "Enhanced RAG Dashboard",
        "namespace": config.rag_namespace
    })

@app.get("/api/stats")
async def get_dashboard_stats():
    """Get dashboard statistics"""
    try:
        if not indexer or not query_engine:
            raise HTTPException(status_code=503, detail="Dashboard not initialized")
        
        indexing_stats = indexer.get_namespace_stats()
        query_stats = query_engine.get_query_stats()
        
        system_health = {
            "api_status": "healthy",
            "database_status": "connected",
            "memory_usage": "N/A",
            "uptime": "N/A"
        }
        
        return {
            "indexing_stats": indexing_stats,
            "query_stats": query_stats,
            "system_health": system_health
        }
        
    except Exception as e:
        logger.error(f"Failed to get dashboard stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

@app.get("/api/documents")
async def get_dashboard_documents():
    """Get documents for dashboard display"""
    try:
        if not indexer:
            raise HTTPException(status_code=503, detail="Dashboard not initialized")
        
        documents = indexer.list_documents(limit=100)
        
        return documents
        
    except Exception as e:
        logger.error(f"Failed to get documents: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get documents: {str(e)}")

@app.post("/api/query")
async def dashboard_query(request: Request):
    """Handle dashboard queries"""
    try:
        if not query_engine:
            raise HTTPException(status_code=503, detail="Dashboard not initialized")
        
        body = await request.json()
        question = body.get("question")
        
        if not question:
            raise HTTPException(status_code=400, detail="Question is required")
        
        result = query_engine.query(question)
        
        return {
            "answer": result.answer,
            "sources": result.sources,
            "query_type": result.query_type.value,
            "confidence": result.confidence,
            "processing_time": result.processing_time,
            "total_chunks_retrieved": result.total_chunks_retrieved,
            "relevant_chunks_used": result.relevant_chunks_used,
            "metadata": result.metadata
        }
        
    except Exception as e:
        logger.error(f"Dashboard query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

@app.post("/api/ingest")
async def dashboard_ingest(request: Request):
    """Handle dashboard document ingestion"""
    try:
        if not indexer:
            raise HTTPException(status_code=503, detail="Dashboard not initialized")
        
        body = await request.json()
        content = body.get("content")
        source = body.get("source", "dashboard_upload")
        
        if not content:
            raise HTTPException(status_code=400, detail="Content is required")
        
        # Create temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name
        
        try:
            result = indexer._index_single_document(temp_path, reindex=False)
            
            if result.success:
                return {
                    "status": "success",
                    "doc_id": result.doc_id,
                    "chunks_created": result.chunks_created,
                    "processing_time": result.duration
                }
            else:
                raise HTTPException(status_code=400, detail=f"Ingestion failed: {result.error}")
                
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except:
                pass
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Dashboard ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

@app.post("/api/ingest/file")
async def dashboard_file_upload(request: Request):
    """Handle dashboard file upload"""
    try:
        if not indexer:
            raise HTTPException(status_code=503, detail="Dashboard not initialized")
        
        # This would need to be implemented with proper file handling
        # For now, return a placeholder response
        raise HTTPException(status_code=501, detail="File upload not implemented in dashboard server")
        
    except Exception as e:
        logger.error(f"Dashboard file upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")

@app.delete("/api/documents/{doc_id}")
async def dashboard_delete_document(doc_id: str):
    """Handle dashboard document deletion"""
    try:
        if not indexer:
            raise HTTPException(status_code=503, detail="Dashboard not initialized")
        
        indexer._delete_document(doc_id)
        
        return {"status": "deleted", "doc_id": doc_id}
        
    except Exception as e:
        logger.error(f"Dashboard document deletion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")

@app.get("/api/health")
async def dashboard_health():
    """Dashboard health check"""
    try:
        if not indexer or not query_engine:
            return {"status": "unhealthy", "reason": "Components not initialized"}
        
        # Test basic functionality
        stats = indexer.get_namespace_stats()
        
        return {
            "status": "healthy",
            "namespace": config.rag_namespace,
            "vector_count": stats.get("vector_count", 0),
            "timestamp": json.dumps({"timestamp": "now"})
        }
        
    except Exception as e:
        logger.error(f"Dashboard health check failed: {e}")
        return {"status": "unhealthy", "reason": str(e)}

if __name__ == "__main__":
    import uvicorn
    
    # Check if dashboard files exist
    if not dashboard_dir.exists():
        print(f"Dashboard directory not found: {dashboard_dir}")
        print("Please ensure the dashboard files are in the correct location.")
        exit(1)
    
    print("🚀 Starting Enhanced RAG Dashboard...")
    print(f"📁 Dashboard directory: {dashboard_dir}")
    print(f"🌐 Dashboard will be available at: http://localhost:8080")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info"
    )
