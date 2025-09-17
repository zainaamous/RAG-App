"""
Tests for configuration system
"""
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch

from config import ConfigManager, RAGConfig, EmbeddingConfig, LLMConfig

class TestConfigManager:
    """Test configuration manager"""
    
    def test_default_config(self):
        """Test default configuration values"""
        with patch.dict(os.environ, {}, clear=True):
            config_manager = ConfigManager()
            config = config_manager.get_config()
            
            assert config.rag_namespace == "library-global"
            assert config.chunking.chunk_size == 1000
            assert config.chunking.chunk_overlap == 200
            assert config.embedding.model == "models/text-embedding-004"
            assert config.llm.model == "gemini-2.5-flash"
    
    def test_env_variable_loading(self):
        """Test environment variable loading"""
        env_vars = {
            "RAG_NAMESPACE": "test-namespace",
            "CHUNK_SIZE": "2000",
            "CHUNK_OVERLAP": "400"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config_manager = ConfigManager()
            config = config_manager.get_config()
            
            assert config.rag_namespace == "test-namespace"
            assert config.chunking.chunk_size == 2000
            assert config.chunking.chunk_overlap == 400
    
    def test_yaml_config_loading(self):
        """Test YAML configuration loading"""
        yaml_content = """
rag_namespace: yaml-namespace
chunking:
  chunk_size: 1500
  chunk_overlap: 300
embedding:
  model: models/custom-embedding
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_file = f.name
        
        try:
            config_manager = ConfigManager(temp_file)
            config = config_manager.get_config()
            
            assert config.rag_namespace == "yaml-namespace"
            assert config.chunking.chunk_size == 1500
            assert config.chunking.chunk_overlap == 300
            assert config.embedding.model == "models/custom-embedding"
            
        finally:
            os.unlink(temp_file)
    
    def test_config_validation(self):
        """Test configuration validation"""
        # Test invalid chunk overlap
        with patch.dict(os.environ, {"CHUNK_OVERLAP": "2000", "CHUNK_SIZE": "1000"}, clear=True):
            with pytest.raises(ValueError, match="CHUNK_OVERLAP must be less than CHUNK_SIZE"):
                ConfigManager()
    
    def test_missing_api_keys(self):
        """Test validation with missing API keys"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="GOOGLE_API_KEY is required"):
                ConfigManager()
    
    def test_config_update(self):
        """Test configuration updates"""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test", "PINECONE_API_KEY": "test"}, clear=True):
            config_manager = ConfigManager()
            
            config_manager.update_config(rag_namespace="updated-namespace")
            config = config_manager.get_config()
            
            assert config.rag_namespace == "updated-namespace"
    
    def test_config_save(self):
        """Test configuration saving"""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test", "PINECONE_API_KEY": "test"}, clear=True):
            config_manager = ConfigManager()
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                temp_file = f.name
            
            try:
                config_manager.save_config(temp_file)
                assert Path(temp_file).exists()
                
                # Verify content
                with open(temp_file, 'r') as f:
                    content = f.read()
                    assert "rag_namespace" in content
                    assert "chunking" in content
                    
            finally:
                os.unlink(temp_file)

class TestConfigClasses:
    """Test configuration dataclasses"""
    
    def test_embedding_config(self):
        """Test embedding configuration"""
        config = EmbeddingConfig()
        assert config.model == "models/text-embedding-004"
        assert config.batch_size == 100
        assert config.max_retries == 3
        assert config.timeout == 30
    
    def test_llm_config(self):
        """Test LLM configuration"""
        config = LLMConfig()
        assert config.model == "gemini-2.5-flash"
        assert config.provider == "google_genai"
        assert config.temperature == 0.1
        assert config.max_tokens == 2048
        assert config.timeout == 60
    
    def test_chunking_config_separators(self):
        """Test chunking configuration separators"""
        config = RAGConfig()
        assert config.chunking.separators == ["\n## ", "\n# ", "\n\n", "\n", " "]
