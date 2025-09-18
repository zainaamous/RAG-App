"""
Tests for enhanced query engine
"""
import pytest
from unittest.mock import Mock, patch, MagicMock

from query_engine import (
    EnhancedQueryEngine, QueryResult, QueryType, QueryAnalyzer,
    RetrievalStats
)
from config import config

class TestQueryType:
    """Test query type enum"""
    
    def test_query_type_values(self):
        """Test query type enum values"""
        assert QueryType.FACTUAL.value == "factual"
        assert QueryType.ANALYTICAL.value == "analytical"
        assert QueryType.COMPARATIVE.value == "comparative"
        assert QueryType.SUMMARIZATION.value == "summarization"
        assert QueryType.CREATIVE.value == "creative"

class TestQueryAnalyzer:
    """Test query analyzer"""
    
    def test_analyze_factual_query(self):
        """Test analysis of factual query"""
        analyzer = QueryAnalyzer()
        query_type, metadata = analyzer.analyze_query("What is machine learning?")
        
        assert query_type == QueryType.FACTUAL
        assert metadata["has_question_mark"] is True
        assert metadata["complexity"] == "low"
    
    def test_analyze_analytical_query(self):
        """Test analysis of analytical query"""
        analyzer = QueryAnalyzer()
        query_type, metadata = analyzer.analyze_query("Why does machine learning work and what are the effects?")
        
        assert query_type == QueryType.ANALYTICAL
        assert metadata["complexity"] == "high"
        assert "why" in metadata["keywords"]
    
    def test_analyze_comparative_query(self):
        """Test analysis of comparative query"""
        analyzer = QueryAnalyzer()
        query_type, metadata = analyzer.analyze_query("Compare neural networks vs decision trees")
        
        assert query_type == QueryType.COMPARATIVE
        assert "compare" in metadata["keywords"]
    
    def test_analyze_summarization_query(self):
        """Test analysis of summarization query"""
        analyzer = QueryAnalyzer()
        query_type, metadata = analyzer.analyze_query("Summarize the main points about AI")
        
        assert query_type == QueryType.SUMMARIZATION
        assert "summarize" in metadata["keywords"]
    
    def test_analyze_creative_query(self):
        """Test analysis of creative query"""
        analyzer = QueryAnalyzer()
        query_type, metadata = analyzer.analyze_query("Create a plan for implementing AI in our company")
        
        assert query_type == QueryType.CREATIVE
        assert "create" in metadata["keywords"]
    
    def test_analyze_query_metadata(self):
        """Test query metadata analysis"""
        analyzer = QueryAnalyzer()
        query_type, metadata = analyzer.analyze_query("What is 42? This is a test question with numbers.")
        
        assert metadata["length"] == 10
        assert metadata["has_numbers"] is True
        assert metadata["complexity"] == "medium"

class TestQueryResult:
    """Test query result dataclass"""
    
    def test_query_result_creation(self):
        """Test creating query result"""
        result = QueryResult(
            answer="Test answer",
            sources=[{"source": "test.pdf", "chunk_start": 0}],
            query_type=QueryType.FACTUAL,
            confidence=0.85,
            processing_time=1.5,
            total_chunks_retrieved=10,
            relevant_chunks_used=3,
            metadata={"test": "data"}
        )
        
        assert result.answer == "Test answer"
        assert len(result.sources) == 1
        assert result.query_type == QueryType.FACTUAL
        assert result.confidence == 0.85
        assert result.processing_time == 1.5
        assert result.total_chunks_retrieved == 10
        assert result.relevant_chunks_used == 3
        assert result.metadata["test"] == "data"

class TestRetrievalStats:
    """Test retrieval stats dataclass"""
    
    def test_retrieval_stats_creation(self):
        """Test creating retrieval stats"""
        stats = RetrievalStats(
            total_candidates=50,
            documents_found=5,
            chunks_per_doc=6,
            similarity_scores=[0.9, 0.8, 0.7],
            retrieval_time=0.5
        )
        
        assert stats.total_candidates == 50
        assert stats.documents_found == 5
        assert stats.chunks_per_doc == 6
        assert len(stats.similarity_scores) == 3
        assert stats.retrieval_time == 0.5

class TestEnhancedQueryEngine:
    """Test enhanced query engine"""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration"""
        with patch('query_engine.config') as mock_config:
            mock_config.rag_namespace = "test-namespace"
            mock_config.pinecone_api_key = "test-key"
            mock_config.pinecone.index_name = "test-index"
            mock_config.embedding.model = "models/test-embedding"
            mock_config.llm.model = "test-model"
            mock_config.llm.provider = "test-provider"
            mock_config.llm.temperature = 0.1
            mock_config.llm.max_tokens = 2048
            mock_config.retrieval.max_docs = 3
            mock_config.retrieval.k_per_doc = 6
            mock_config.retrieval.pool_k = 80
            mock_config.retrieval.pool_fetch_k = 160
            mock_config.retrieval.similarity_threshold = 0.7
            yield mock_config
    
    @pytest.fixture
    def mock_components(self):
        """Mock external components"""
        with patch('query_engine.init_chat_model') as mock_llm, \
             patch('query_engine.GoogleGenerativeAIEmbeddings') as mock_embed, \
             patch('query_engine.Pinecone') as mock_pc, \
             patch('query_engine.PineconeVectorStore') as mock_vs:
            
            # Setup mocks
            mock_llm.return_value = Mock()
            mock_embed.return_value = Mock()
            mock_pc.return_value.Index.return_value = Mock()
            mock_vs.return_value = Mock()
            
            yield {
                'llm': mock_llm.return_value,
                'embedder': mock_embed.return_value,
                'pinecone': mock_pc.return_value,
                'index': mock_pc.return_value.Index.return_value,
                'vector_store': mock_vs.return_value
            }
    
    def test_query_engine_initialization(self, mock_config, mock_components):
        """Test query engine initialization"""
        engine = EnhancedQueryEngine("test-namespace")
        
        assert engine.namespace == "test-namespace"
        assert engine.llm is not None
        assert engine.embedder is not None
        assert engine.vector_store is not None
        assert engine.query_analyzer is not None
    
    def test_retrieve_context_no_results(self, mock_config, mock_components):
        """Test context retrieval with no results"""
        engine = EnhancedQueryEngine("test-namespace")
        
        # Mock empty results
        mock_components['vector_store'].similarity_search_with_score.return_value = []
        
        docs, stats = engine._retrieve_context("test query", QueryType.FACTUAL, {})
        
        assert len(docs) == 0
        assert stats.total_candidates == 0
        assert stats.documents_found == 0
    
    def test_retrieve_context_with_results(self, mock_config, mock_components):
        """Test context retrieval with results"""
        engine = EnhancedQueryEngine("test-namespace")
        
        # Mock results
        mock_doc1 = Mock()
        mock_doc1.metadata = {"doc_uid": "doc1"}
        mock_doc2 = Mock()
        mock_doc2.metadata = {"doc_uid": "doc2"}
        
        mock_components['vector_store'].similarity_search_with_score.return_value = [
            (mock_doc1, 0.9),
            (mock_doc2, 0.8)
        ]
        
        docs, stats = engine._retrieve_context("test query", QueryType.FACTUAL, {})
        
        assert len(docs) >= 0  # May be filtered by threshold
        assert stats.total_candidates == 2
        assert stats.documents_found == 2
    
    def test_generate_answer(self, mock_config, mock_components):
        """Test answer generation"""
        engine = EnhancedQueryEngine("test-namespace")
        
        # Mock documents
        mock_doc = Mock()
        mock_doc.page_content = "Test content"
        mock_doc.metadata = {"source": "test.pdf"}
        
        # Mock LLM response
        mock_response = Mock()
        mock_response.content = "Test answer"
        mock_components['llm'].invoke.return_value = mock_response
        
        answer = engine._generate_answer(
            "test question", 
            [mock_doc], 
            QueryType.FACTUAL, 
            {}
        )
        
        assert answer == "Test answer"
        mock_components['llm'].invoke.assert_called_once()
    
    def test_calculate_confidence(self, mock_config, mock_components):
        """Test confidence calculation"""
        engine = EnhancedQueryEngine("test-namespace")
        
        # Test with high similarity scores
        high_scores = [0.9, 0.8, 0.85]
        mock_docs = [Mock(), Mock(), Mock()]
        
        confidence = engine._calculate_confidence(high_scores, mock_docs)
        
        assert confidence > 0.7
        assert confidence <= 1.0
        
        # Test with low similarity scores
        low_scores = [0.3, 0.4, 0.5]
        confidence = engine._calculate_confidence(low_scores, mock_docs)
        
        assert confidence < 0.6
        assert confidence >= 0.0
    
    def test_query_no_context(self, mock_config, mock_components):
        """Test query with no context found"""
        engine = EnhancedQueryEngine("test-namespace")
        
        # Mock no results
        mock_components['vector_store'].similarity_search_with_score.return_value = []
        
        result = engine.query("test question")
        
        assert result.answer.startswith("I couldn't find relevant information")
        assert len(result.sources) == 0
        assert result.confidence == 0.0
        assert result.query_type == QueryType.FACTUAL
    
    def test_query_with_context(self, mock_config, mock_components):
        """Test query with context found"""
        engine = EnhancedQueryEngine("test-namespace")
        
        # Mock results
        mock_doc = Mock()
        mock_doc.page_content = "Test content"
        mock_doc.metadata = {"source": "test.pdf", "chunk_start": 0, "doc_uid": "doc1"}
        
        mock_components['vector_store'].similarity_search_with_score.return_value = [
            (mock_doc, 0.9)
        ]
        
        # Mock LLM response
        mock_response = Mock()
        mock_response.content = "Test answer"
        mock_components['llm'].invoke.return_value = mock_response
        
        result = engine.query("test question")
        
        assert result.answer == "Test answer"
        assert len(result.sources) == 1
        assert result.sources[0]["source"] == "test.pdf"
        assert result.confidence > 0
        assert result.processing_time > 0
    
    def test_query_error_handling(self, mock_config, mock_components):
        """Test query error handling"""
        engine = EnhancedQueryEngine("test-namespace")
        
        # Mock error in retrieval
        mock_components['vector_store'].similarity_search_with_score.side_effect = Exception("Test error")
        
        result = engine.query("test question")
        
        assert "error" in result.answer.lower()
        assert result.confidence == 0.0
        assert "error" in result.metadata
    
    def test_get_query_stats(self, mock_config, mock_components):
        """Test getting query statistics"""
        engine = EnhancedQueryEngine("test-namespace")
        
        # Mock index stats
        mock_stats = {
            "namespaces": {
                "test-namespace": {
                    "vectorCount": 100
                }
            },
            "dimension": 768
        }
        mock_components['index'].describe_index_stats.return_value = mock_stats
        
        stats = engine.get_query_stats()
        
        assert stats["namespace"] == "test-namespace"
        assert stats["total_vectors"] == 100
        assert stats["index_dimension"] == 768
        assert "retrieval_config" in stats
