"""
Tests for enhanced API
"""
import pytest
import tempfile
import json
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

from api_v2 import app, manager
from indexer import IndexingResult
from query_engine import QueryResult, QueryType


@pytest.fixture
def client():
    """Test client for API"""
    return TestClient(app)

@pytest.fixture
def mock_config():
    """Mock configuration"""
    with patch('api_v2.config') as mock_config:
        mock_config.rag_namespace = "test-namespace"
        mock_config.pinecone.index_name = "test-index"
        mock_config.pinecone_api_key = "test-key"
        mock_config.google_api_key = "test-key"
        yield mock_config

@pytest.fixture
def mock_indexer():
    """Mock indexer"""
    with patch('api_v2.EnhancedIndexer') as mock_indexer_class:
        mock_indexer = Mock()
        mock_indexer_class.return_value = mock_indexer
        yield mock_indexer

@pytest.fixture
def mock_query_engine():
    """Mock query engine"""
    with patch('api_v2.EnhancedQueryEngine') as mock_engine_class:
        mock_engine = Mock()
        mock_engine_class.return_value = mock_engine
        yield mock_engine

class TestHealthEndpoint:
    """Test health endpoint"""
    
    def test_health_check_success(self, client, mock_config, mock_indexer):
        """Test successful health check"""
        # Mock indexer stats
        mock_indexer.get_namespace_stats.return_value = {
            "vector_count": 100,
            "index_dimension": 768
        }
        
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["namespace"] == "test-namespace"
        assert data["vector_count"] == 100
    
    def test_health_check_error(self, client, mock_config, mock_indexer):
        """Test health check with error"""
        mock_indexer.get_namespace_stats.side_effect = Exception("Test error")
        
        response = client.get("/health")
        
        assert response.status_code == 500
        assert "Health check failed" in response.json()["detail"]

class TestIngestEndpoint:
    """Test ingest endpoint"""
    
    def test_ingest_success(self, client, mock_config, mock_indexer):
        """Test successful document ingestion"""
        # Mock successful indexing
        mock_result = IndexingResult(
            success=True,
            doc_id="test123",
            source="test.txt",
            chunks_created=5,
            duration=1.5
        )
        mock_indexer._index_single_document.return_value = mock_result
        
        payload = {
            "content": "Test document content",
            "source": "test.txt"
        }
        
        response = client.post("/ingest", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["doc_id"] == "test123"
        assert data["status"] == "indexed"
        assert data["chunk_count"] == 5
    
    def test_ingest_failure(self, client, mock_config, mock_indexer):
        """Test document ingestion failure"""
        # Mock failed indexing
        mock_result = IndexingResult(
            success=False,
            doc_id="test123",
            source="test.txt",
            chunks_created=0,
            error="Indexing failed",
            duration=1.0
        )
        mock_indexer._index_single_document.return_value = mock_result
        
        payload = {
            "content": "Test document content"
        }
        
        response = client.post("/ingest", json=payload)
        
        assert response.status_code == 400
        assert "Ingestion failed" in response.json()["detail"]

class TestQueryEndpoint:
    """Test query endpoint"""
    
    def test_query_success(self, client, mock_config, mock_query_engine):
        """Test successful query"""
        # Mock query result
        mock_result = QueryResult(
            answer="Test answer",
            sources=[{"source": "test.pdf", "chunk_start": 0}],
            query_type=QueryType.FACTUAL,
            confidence=0.85,
            processing_time=1.5,
            total_chunks_retrieved=10,
            relevant_chunks_used=3,
            metadata={}
        )
        mock_query_engine.query.return_value = mock_result
        
        payload = {
            "question": "What is machine learning?"
        }
        
        response = client.post("/query", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Test answer"
        assert data["confidence"] == 0.85
        assert data["query_type"] == "factual"
        assert len(data["sources"]) == 1
    
    def test_query_with_parameters(self, client, mock_config, mock_query_engine):
        """Test query with custom parameters"""
        mock_result = QueryResult(
            answer="Test answer",
            sources=[],
            query_type=QueryType.FACTUAL,
            confidence=0.8,
            processing_time=1.0,
            total_chunks_retrieved=5,
            relevant_chunks_used=2,
            metadata={}
        )
        mock_query_engine.query.return_value = mock_result
        
        payload = {
            "question": "Test question",
            "max_docs": 5,
            "k_per_doc": 10,
            "similarity_threshold": 0.8
        }
        
        response = client.post("/query", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Test answer"

class TestFileUploadEndpoint:
    """Test file upload endpoint"""
    
    def test_file_upload_success(self, client, mock_config, mock_indexer):
        """Test successful file upload"""
        mock_result = IndexingResult(
            success=True,
            doc_id="test123",
            source="test.pdf",
            chunks_created=10,
            duration=2.0
        )
        mock_indexer._index_single_document.return_value = mock_result
        
        # Create test file
        test_content = b"Test PDF content"
        
        response = client.post(
            "/ingest/file",
            files={"file": ("test.pdf", test_content, "application/pdf")},
            data={"namespace": "test-namespace"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "indexed"
        assert data["filename"] == "test.pdf"
        assert data["chunks_created"] == 10

class TestDocumentManagement:
    """Test document management endpoints"""
    
    def test_list_documents(self, client, mock_config, mock_indexer):
        """Test listing documents"""
        mock_documents = [
            {
                "doc_uid": "doc1",
                "source": "test1.pdf",
                "chunk_count": 5,
                "version": "2.0"
            },
            {
                "doc_uid": "doc2", 
                "source": "test2.pdf",
                "chunk_count": 8,
                "version": "2.0"
            }
        ]
        mock_indexer.list_documents.return_value = mock_documents
        
        response = client.get("/documents")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["doc_uid"] == "doc1"
        assert data[1]["doc_uid"] == "doc2"
    
    def test_delete_document(self, client, mock_config, mock_indexer):
        """Test document deletion"""
        mock_indexer._delete_document.return_value = None
        
        response = client.delete("/documents/test123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deleted"
        assert data["doc_id"] == "test123"

class TestBatchOperations:
    """Test batch operations"""
    
    def test_batch_ingest(self, client, mock_config, mock_indexer):
        """Test batch document ingestion"""
        # Mock successful indexing for all documents
        mock_result = IndexingResult(
            success=True,
            doc_id="test123",
            source="test.txt",
            chunks_created=5,
            duration=1.0
        )
        mock_indexer._index_single_document.return_value = mock_result
        
        payload = {
            "documents": [
                {"content": "Document 1 content"},
                {"content": "Document 2 content"},
                {"content": "Document 3 content"}
            ]
        }
        
        response = client.post("/ingest/batch", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert data["successful"] == 3
        assert data["failed"] == 0

class TestStreamingQuery:
    """Test streaming query endpoint"""
    
    def test_stream_query(self, client, mock_config, mock_query_engine):
        """Test streaming query response"""
        mock_result = QueryResult(
            answer="This is a test answer with multiple parts.",
            sources=[{"source": "test.pdf"}],
            query_type=QueryType.FACTUAL,
            confidence=0.8,
            processing_time=1.0,
            total_chunks_retrieved=5,
            relevant_chunks_used=2,
            metadata={}
        )
        mock_query_engine.query.return_value = mock_result
        
        payload = {
            "question": "Test question",
            "chunk_size": 10
        }
        
        response = client.post("/query/stream", json=payload)
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; charset=utf-8"

class TestSystemStats:
    """Test system statistics endpoint"""
    
    def test_system_stats(self, client, mock_config, mock_indexer, mock_query_engine):
        """Test system statistics"""
        mock_indexer.get_namespace_stats.return_value = {
            "vector_count": 100,
            "index_dimension": 768
        }
        
        mock_query_engine.get_query_stats.return_value = {
            "total_vectors": 100,
            "retrieval_config": {}
        }
        
        response = client.get("/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert "indexing_stats" in data
        assert "query_stats" in data
        assert "system_health" in data

class TestConfiguration:
    """Test configuration endpoints"""
    
    def test_reload_config(self, client):
        """Test configuration reload"""
        response = client.post("/config/reload")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "reloaded"

class TestWebSocket:
    """Test WebSocket functionality"""
    
    def test_websocket_connection(self, client):
        """Test WebSocket connection"""
        with client.websocket_connect("/ws") as websocket:
            # Send ping message
            websocket.send_text(json.dumps({"type": "ping"}))
            
            # Receive pong response
            data = websocket.receive_text()
            response = json.loads(data)
            
            assert response["type"] == "pong"

class TestErrorHandling:
    """Test error handling"""
    
    def test_invalid_json(self, client):
        """Test invalid JSON handling"""
        response = client.post(
            "/ingest",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_missing_required_fields(self, client):
        """Test missing required fields"""
        payload = {}  # Missing required 'content' field
        
        response = client.post("/ingest", json=payload)
        
        assert response.status_code == 422
    
    def test_invalid_parameters(self, client):
        """Test invalid parameters"""
        payload = {
            "question": "Test question",
            "max_docs": 50,  # Exceeds maximum of 10
            "similarity_threshold": 1.5  # Exceeds maximum of 1.0
        }
        
        response = client.post("/query", json=payload)
        
        assert response.status_code == 422

