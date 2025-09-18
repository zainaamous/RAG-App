"""
Tests for enhanced indexer
"""
import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from indexer import EnhancedIndexer, IndexingResult, IndexingStats
from config import config

class TestIndexingResult:
    """Test indexing result dataclass"""
    
    def test_indexing_result_creation(self):
        """Test creating indexing result"""
        result = IndexingResult(
            success=True,
            doc_id="test123",
            source="/path/to/file.pdf",
            chunks_created=5,
            duration=1.5
        )
        
        assert result.success is True
        assert result.doc_id == "test123"
        assert result.source == "/path/to/file.pdf"
        assert result.chunks_created == 5
        assert result.duration == 1.5
        assert result.error is None
    
    def test_indexing_result_with_error(self):
        """Test indexing result with error"""
        result = IndexingResult(
            success=False,
            doc_id="test123",
            source="/path/to/file.pdf",
            chunks_created=0,
            error="Test error",
            duration=0.5
        )
        
        assert result.success is False
        assert result.error == "Test error"

class TestIndexingStats:
    """Test indexing stats dataclass"""
    
    def test_indexing_stats_creation(self):
        """Test creating indexing stats"""
        stats = IndexingStats(
            total_files=10,
            successful=8,
            failed=1,
            skipped=1,
            total_chunks=40,
            duration=5.0,
            errors=["Error 1"]
        )
        
        assert stats.total_files == 10
        assert stats.successful == 8
        assert stats.failed == 1
        assert stats.skipped == 1
        assert stats.total_chunks == 40
        assert stats.duration == 5.0
        assert len(stats.errors) == 1

class TestEnhancedIndexer:
    """Test enhanced indexer"""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration"""
        with patch('indexer.config') as mock_config:
            mock_config.rag_namespace = "test-namespace"
            mock_config.pinecone_api_key = "test-key"
            mock_config.pinecone.index_name = "test-index"
            mock_config.chunking.chunk_size = 1000
            mock_config.chunking.chunk_overlap = 200
            mock_config.chunking.separators = ["\n\n", "\n", " "]
            mock_config.doc_id_hash_mode = "PATH"
            mock_config.user_agent = "test-agent"
            yield mock_config
    
    @pytest.fixture
    def mock_components(self):
        """Mock external components"""
        with patch('indexer.GoogleGenerativeAIEmbeddings') as mock_embed, \
             patch('indexer.Pinecone') as mock_pc, \
             patch('indexer.PineconeVectorStore') as mock_vs, \
             patch('indexer.RecursiveCharacterTextSplitter') as mock_splitter:
            
            # Setup mocks
            mock_embed.return_value = Mock()
            mock_pc.return_value.Index.return_value = Mock()
            mock_vs.return_value = Mock()
            mock_splitter.return_value = Mock()
            
            yield {
                'embedder': mock_embed.return_value,
                'pinecone': mock_pc.return_value,
                'index': mock_pc.return_value.Index.return_value,
                'vector_store': mock_vs.return_value,
                'splitter': mock_splitter.return_value
            }
    
    def test_indexer_initialization(self, mock_config, mock_components):
        """Test indexer initialization"""
        indexer = EnhancedIndexer("test-namespace")
        
        assert indexer.namespace == "test-namespace"
        assert indexer.embedder is not None
        assert indexer.pinecone_client is not None
        assert indexer.index is not None
        assert indexer.vector_store is not None
        assert indexer.splitter is not None
    
    def test_build_chunk_ids(self, mock_config, mock_components):
        """Test chunk ID generation"""
        indexer = EnhancedIndexer("test-namespace")
        
        ids = indexer._build_chunk_ids("doc123", 5)
        
        expected = [
            "test-namespace:doc123:0000000",
            "test-namespace:doc123:0000001",
            "test-namespace:doc123:0000002",
            "test-namespace:doc123:0000003",
            "test-namespace:doc123:0000004"
        ]
        
        assert ids == expected
    
    def test_sentinel_id(self, mock_config, mock_components):
        """Test sentinel ID generation"""
        indexer = EnhancedIndexer("test-namespace")
        
        sentinel_id = indexer._sentinel_id("doc123")
        
        assert sentinel_id == "test-namespace:doc123:SENTINEL"
    
    def test_sentinel_exists_true(self, mock_config, mock_components):
        """Test sentinel exists when it does"""
        indexer = EnhancedIndexer("test-namespace")
        
        # Mock index.fetch to return sentinel
        mock_components['index'].fetch.return_value.vectors = {"test-namespace:doc123:SENTINEL": Mock()}
        
        exists = indexer._sentinel_exists("doc123")
        
        assert exists is True
    
    def test_sentinel_exists_false(self, mock_config, mock_components):
        """Test sentinel exists when it doesn't"""
        indexer = EnhancedIndexer("test-namespace")
        
        # Mock index.fetch to return empty
        mock_components['index'].fetch.return_value.vectors = {}
        
        exists = indexer._sentinel_exists("doc123")
        
        assert exists is False
    
    @patch('indexer.load_one_local')
    def test_index_single_document_success(self, mock_load, mock_config, mock_components):
        """Test successful single document indexing"""
        # Setup mocks
        mock_docs = [Mock(page_content="Test content", metadata={"start_index": 0})]
        mock_chunks = [Mock(page_content="Test chunk", metadata={})]
        
        mock_load.return_value = mock_docs
        mock_components['splitter'].split_documents.return_value = mock_chunks
        mock_components['vector_store'].add_documents.return_value = ["chunk1", "chunk2"]
        mock_components['embedder'].embed_query.return_value = [0.1, 0.2, 0.3]
        
        indexer = EnhancedIndexer("test-namespace")
        
        # Create temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test content")
            temp_file = f.name
        
        try:
            result = indexer._index_single_document(temp_file)
            
            assert result.success is True
            assert result.chunks_created == 2
            assert result.duration > 0
            
        finally:
            os.unlink(temp_file)
    
    @patch('indexer.iter_files')
    def test_index_paths_no_files(self, mock_iter_files, mock_config, mock_components):
        """Test indexing when no files found"""
        mock_iter_files.return_value = []
        
        indexer = EnhancedIndexer("test-namespace")
        stats = indexer.index_paths(["/nonexistent/path"])
        
        assert stats.total_files == 0
        assert stats.successful == 0
        assert stats.failed == 0
    
    def test_get_namespace_stats(self, mock_config, mock_components):
        """Test getting namespace statistics"""
        # Mock index stats
        mock_stats = {
            "namespaces": {
                "test-namespace": {
                    "vectorCount": 100
                }
            },
            "dimension": 768,
            "metric": "cosine"
        }
        mock_components['index'].describe_index_stats.return_value = mock_stats
        
        indexer = EnhancedIndexer("test-namespace")
        stats = indexer.get_namespace_stats()
        
        assert stats["namespace"] == "test-namespace"
        assert stats["vector_count"] == 100
        assert stats["index_dimension"] == 768
        assert stats["index_metric"] == "cosine"
    
    def test_list_documents(self, mock_config, mock_components):
        """Test listing documents"""
        # Mock query response
        mock_match = Mock()
        mock_match.metadata = {
            "doc_uid": "doc123",
            "source": "/path/to/file.pdf",
            "chunk_count": 5,
            "indexed_at": 1234567890,
            "version": "2.0"
        }
        
        mock_response = Mock()
        mock_response.matches = [mock_match]
        mock_components['index'].query.return_value = mock_response
        
        indexer = EnhancedIndexer("test-namespace")
        documents = indexer.list_documents(10)
        
        assert len(documents) == 1
        assert documents[0]["doc_uid"] == "doc123"
        assert documents[0]["source"] == "/path/to/file.pdf"
        assert documents[0]["chunk_count"] == 5
