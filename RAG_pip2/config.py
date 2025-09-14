"""
Enhanced Configuration Management System
Supports multiple environments, validation, and better error handling
"""
import os
import getpass
import json
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, asdict
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class EmbeddingConfig:
    """Configuration for embedding models"""
    model: str = "models/text-embedding-004"
    batch_size: int = 100
    max_retries: int = 3
    timeout: int = 30

@dataclass
class LLMConfig:
    """Configuration for Language Models"""
    model: str = "gemini-2.5-flash"
    provider: str = "google_genai"
    temperature: float = 0.1
    max_tokens: int = 2048
    timeout: int = 60

@dataclass
class ChunkingConfig:
    """Configuration for document chunking"""
    chunk_size: int = 1000
    chunk_overlap: int = 200
    separators: list = None
    
    def __post_init__(self):
        if self.separators is None:
            self.separators = ["\n## ", "\n# ", "\n\n", "\n", " "]

@dataclass
class RetrievalConfig:
    """Configuration for retrieval parameters"""
    max_docs: int = 3
    k_per_doc: int = 6
    pool_k: int = 80
    pool_fetch_k: int = 160
    similarity_threshold: float = 0.7

@dataclass
class PineconeConfig:
    """Configuration for Pinecone"""
    api_key: str = ""
    index_name: str = "mahmoud"
    environment: str = "us-west1-gcp"
    dimension: int = 768

@dataclass
class APIConfig:
    """Configuration for API server"""
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = True
    workers: int = 1
    log_level: str = "info"

@dataclass
class RAGConfig:
    """Main RAG configuration"""
    # API Keys
    google_api_key: str = ""
    pinecone_api_key: str = ""
    
    # Core settings
    rag_namespace: str = "library-global"
    user_agent: str = "rag-enhanced/2.0 (+rag@example.com)"
    doc_id_hash_mode: str = "PATH"  # PATH or CONTENT
    
    # Component configurations
    embedding: EmbeddingConfig = None
    llm: LLMConfig = None
    chunking: ChunkingConfig = None
    retrieval: RetrievalConfig = None
    pinecone: PineconeConfig = None
    api: APIConfig = None
    
    def __post_init__(self):
        if self.embedding is None:
            self.embedding = EmbeddingConfig()
        if self.llm is None:
            self.llm = LLMConfig()
        if self.chunking is None:
            self.chunking = ChunkingConfig()
        if self.retrieval is None:
            self.retrieval = RetrievalConfig()
        if self.pinecone is None:
            self.pinecone = PineconeConfig()
        if self.api is None:
            self.api = APIConfig()

class ConfigManager:
    """Enhanced configuration manager with validation and multiple sources"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or "rag_config.yaml"
        self.config = RAGConfig()
        self._load_config()
    
    def _env(self, name: str, prompt: str = None, default: str = None, sensitive: bool = False) -> str:
        """Enhanced environment variable loading with better UX"""
        val = os.environ.get(name)
        
        if not val and prompt:
            if sensitive:
                val = getpass.getpass(prompt)
            else:
                val = input(prompt)
            os.environ[name] = val
            
        return val or default or ""
    
    def _load_config(self):
        """Load configuration from multiple sources with priority order"""
        # 1. Load from YAML file if exists
        if Path(self.config_file).exists():
            self._load_from_yaml()
        
        # 2. Load from environment variables (highest priority)
        self._load_from_env()
        
        # 3. Validate configuration
        self._validate_config()
    
    def _load_from_yaml(self):
        """Load configuration from YAML file"""
        try:
            with open(self.config_file, 'r') as f:
                data = yaml.safe_load(f)
                if data:
                    # Update config with YAML data
                    for key, value in data.items():
                        if hasattr(self.config, key):
                            setattr(self.config, key, value)
            logger.info(f"Loaded configuration from {self.config_file}")
        except Exception as e:
            logger.warning(f"Failed to load YAML config: {e}")
    
    def _load_from_env(self):
        """Load configuration from environment variables"""
        # API Keys (required)
        self.config.google_api_key = self._env(
            "GOOGLE_API_KEY", 
            "Enter Google API key: ", 
            sensitive=True
        )
        self.config.pinecone_api_key = self._env(
            "PINECONE_API_KEY", 
            "Enter Pinecone API key: ", 
            sensitive=True
        )
        
        # Core settings
        self.config.rag_namespace = self._env("RAG_NAMESPACE", default="library-global")
        self.config.user_agent = self._env("USER_AGENT", default="rag-enhanced/2.0")
        self.config.doc_id_hash_mode = self._env("DOC_ID_HASH_MODE", default="PATH").upper()
        
        # Pinecone settings
        self.config.pinecone.index_name = self._env("PINECONE_INDEX", default="mahmoud")
        self.config.pinecone.environment = self._env("PINECONE_ENVIRONMENT", default="us-west1-gcp")
        
        # Chunking settings
        chunk_size = self._env("CHUNK_SIZE", default="1000")
        chunk_overlap = self._env("CHUNK_OVERLAP", default="200")
        if chunk_size.isdigit():
            self.config.chunking.chunk_size = int(chunk_size)
        if chunk_overlap.isdigit():
            self.config.chunking.chunk_overlap = int(chunk_overlap)
        
        # API settings
        api_port = self._env("API_PORT", default="8000")
        if api_port.isdigit():
            self.config.api.port = int(api_port)
        self.config.api.host = self._env("API_HOST", default="0.0.0.0")
        self.config.api.log_level = self._env("API_LOG_LEVEL", default="info")
    
    def _validate_config(self):
        """Validate configuration and provide helpful error messages"""
        errors = []
        
        if not self.config.google_api_key:
            errors.append("GOOGLE_API_KEY is required")
        
        if not self.config.pinecone_api_key:
            errors.append("PINECONE_API_KEY is required")
        
        if self.config.chunking.chunk_size <= 0:
            errors.append("CHUNK_SIZE must be positive")
        
        if self.config.chunking.chunk_overlap >= self.config.chunking.chunk_size:
            errors.append("CHUNK_OVERLAP must be less than CHUNK_SIZE")
        
        if errors:
            error_msg = "Configuration errors:\n" + "\n".join(f"  - {error}" for error in errors)
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    def save_config(self, file_path: str = None):
        """Save current configuration to YAML file"""
        file_path = file_path or self.config_file
        
        # Convert to dict and remove sensitive data
        config_dict = asdict(self.config)
        config_dict.pop('google_api_key', None)
        config_dict.pop('pinecone_api_key', None)
        
        try:
            with open(file_path, 'w') as f:
                yaml.dump(config_dict, f, default_flow_style=False, indent=2)
            logger.info(f"Configuration saved to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
    
    def get_config(self) -> RAGConfig:
        """Get the current configuration"""
        return self.config
    
    def update_config(self, **kwargs):
        """Update configuration values"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
            else:
                logger.warning(f"Unknown configuration key: {key}")
        
        self._validate_config()

# Global configuration instance
config_manager = ConfigManager()
config = config_manager.get_config()

# Backward compatibility - expose commonly used settings
GOOGLE_API_KEY = config.google_api_key
PINECONE_API_KEY = config.pinecone_api_key
INDEX_NAME = config.pinecone.index_name
RAG_NAMESPACE = config.rag_namespace
USER_AGENT = config.user_agent
CHUNK_SIZE = config.chunking.chunk_size
CHUNK_OVERLAP = config.chunking.chunk_overlap
DOC_ID_HASH_MODE = config.doc_id_hash_mode

# Export for easy access
__all__ = [
    'config', 'config_manager', 'RAGConfig', 'ConfigManager',
    'GOOGLE_API_KEY', 'PINECONE_API_KEY', 'INDEX_NAME', 'RAG_NAMESPACE',
    'USER_AGENT', 'CHUNK_SIZE', 'CHUNK_OVERLAP', 'DOC_ID_HASH_MODE'
]

if __name__ == "__main__":
    # CLI for configuration management
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "save":
            config_manager.save_config()
            print("Configuration saved!")
        elif sys.argv[1] == "validate":
            config_manager._validate_config()
            print("Configuration is valid!")
        elif sys.argv[1] == "show":
            print(json.dumps(asdict(config), indent=2, default=str))
    else:
        print("Usage: python config.py [save|validate|show]")