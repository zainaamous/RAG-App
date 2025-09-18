"""
Pytest configuration and shared fixtures
"""
import pytest
import tempfile
import os
from unittest.mock import patch

@pytest.fixture(scope="session")
def test_env():
    """Set up test environment variables"""
    env_vars = {
        "GOOGLE_API_KEY": "test-google-key",
        "PINECONE_API_KEY": "test-pinecone-key",
        "PINECONE_INDEX": "test-index",
        "RAG_NAMESPACE": "test-namespace",
        "CHUNK_SIZE": "1000",
        "CHUNK_OVERLAP": "200"
    }
    
    with patch.dict(os.environ, env_vars, clear=True):
        yield env_vars

@pytest.fixture
def temp_file():
    """Create a temporary file for testing"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("This is test content for document processing.")
        temp_file_path = f.name
    
    yield temp_file_path
    
    # Cleanup
    try:
        os.unlink(temp_file_path)
    except:
        pass

@pytest.fixture
def sample_documents():
    """Sample documents for testing"""
    return [
        {
            "content": "Machine learning is a subset of artificial intelligence that focuses on algorithms that can learn from data.",
            "source": "ml_basics.txt",
            "doc_id": "doc1"
        },
        {
            "content": "Deep learning uses neural networks with multiple layers to model and understand complex patterns in data.",
            "source": "deep_learning.txt", 
            "doc_id": "doc2"
        },
        {
            "content": "Natural language processing combines computational linguistics with machine learning to help computers understand human language.",
            "source": "nlp_overview.txt",
            "doc_id": "doc3"
        }
    ]

@pytest.fixture
def sample_queries():
    """Sample queries for testing"""
    return [
        {
            "question": "What is machine learning?",
            "expected_type": "factual",
            "keywords": ["machine", "learning", "algorithms"]
        },
        {
            "question": "How does deep learning differ from traditional machine learning?",
            "expected_type": "comparative",
            "keywords": ["deep", "learning", "neural", "networks"]
        },
        {
            "question": "Explain the relationship between AI, ML, and NLP",
            "expected_type": "analytical",
            "keywords": ["relationship", "artificial", "intelligence", "natural", "language"]
        }
    ]

@pytest.fixture(autouse=True)
def mock_external_services():
    """Mock external services to avoid API calls during testing"""
    with patch('langchain_google_genai.GoogleGenerativeAIEmbeddings'), \
         patch('pinecone.Pinecone'), \
         patch('langchain.chat_models.init_chat_model'), \
         patch('langchain.hub.pull'):
        yield
