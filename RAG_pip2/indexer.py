"""
Enhanced Document Indexing System
Improved error handling, monitoring, and performance
"""
import os
import time
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone
from pinecone.exceptions import NotFoundException
from langchain_core.documents import Document

from config import config
from logger import logger, log_operation, log_performance, log_error
from filesys import iter_files, load_one_local, doc_uid_for_path, doc_uid_for_content

@dataclass
class IndexingResult:
    """Result of indexing operation"""
    success: bool
    doc_id: str
    source: str
    chunks_created: int
    error: Optional[str] = None
    duration: float = 0.0

@dataclass
class IndexingStats:
    """Statistics for indexing operation"""
    total_files: int
    successful: int
    failed: int
    skipped: int
    total_chunks: int
    duration: float
    errors: List[str]

class EnhancedIndexer:
    """Enhanced document indexer with better error handling and monitoring"""
    
    def __init__(self, namespace: str = None):
        self.namespace = namespace or config.rag_namespace
        self.embedder = None
        self.pinecone_client = None
        self.index = None
        self.vector_store = None
        self.splitter = None
        self._lock = threading.Lock()
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize all components with error handling"""
        try:
            log_operation("initializing_indexer", namespace=self.namespace)
            
            # Initialize embeddings
            self.embedder = GoogleGenerativeAIEmbeddings(
                model=config.embedding.model,
                request_options={"timeout": config.embedding.timeout}
            )
            
            # Initialize Pinecone
            self.pinecone_client = Pinecone(api_key=config.pinecone_api_key)
            self.index = self.pinecone_client.Index(config.pinecone.index_name)
            
            # Initialize vector store
            self.vector_store = PineconeVectorStore(
                embedding=self.embedder,
                index=self.index
            )
            
            # Initialize text splitter
            self.splitter = RecursiveCharacterTextSplitter(
                chunk_size=config.chunking.chunk_size,
                chunk_overlap=config.chunking.chunk_overlap,
                add_start_index=True,
                separators=config.chunking.separators
            )
            
            logger.info("Indexer components initialized successfully")
            
        except Exception as e:
            log_error(e, "initializing_indexer")
            raise
    
    def _build_chunk_ids(self, doc_uid: str, n: int) -> List[str]:
        """Generate unique IDs for document chunks"""
        return [f"{self.namespace}:{doc_uid}:{i:07d}" for i in range(n)]
    
    def _sentinel_id(self, doc_uid: str) -> str:
        """Generate sentinel ID for document tracking"""
        return f"{self.namespace}:{doc_uid}:SENTINEL"
    
    def _sentinel_exists(self, doc_uid: str) -> bool:
        """Check if document is already indexed"""
        try:
            sid = self._sentinel_id(doc_uid)
            result = self.index.fetch(ids=[sid], namespace=self.namespace)
            return bool(result.vectors and sid in result.vectors)
        except Exception as e:
            log_error(e, "checking_sentinel")
            return False
    
    def _upsert_sentinel(self, doc_uid: str, source: str, chunk_count: int):
        """Insert sentinel vector to mark document as indexed"""
        try:
            sentinel_text = f"sentinel:{doc_uid}:{chunk_count}"
            vec = self.embedder.embed_query(sentinel_text)
            
            self.index.upsert(
                vectors=[{
                    "id": self._sentinel_id(doc_uid),
                    "values": vec,
                    "metadata": {
                        "kind": "sentinel",
                        "doc_uid": doc_uid,
                        "source": source,
                        "chunk_count": chunk_count,
                        "indexed_at": time.time(),
                        "version": "2.0"
                    }
                }],
                namespace=self.namespace
            )
            
            logger.debug("Sentinel upserted", doc_uid=doc_uid, chunk_count=chunk_count)
            
        except Exception as e:
            log_error(e, "upserting_sentinel", doc_uid=doc_uid)
            raise
    
    def _wait_for_indexing(self, expected_increase: int, timeout: float = 30.0):
        """Wait for indexing to complete with timeout"""
        start_time = time.time()
        initial_stats = self.index.describe_index_stats()
        initial_count = initial_stats.get("namespaces", {}).get(self.namespace, {}).get("vectorCount", 0)
        
        while time.time() - start_time < timeout:
            try:
                stats = self.index.describe_index_stats()
                current_count = stats.get("namespaces", {}).get(self.namespace, {}).get("vectorCount", 0)
                
                if current_count >= initial_count + expected_increase:
                    logger.debug("Indexing completed", 
                               initial_count=initial_count, 
                               current_count=current_count,
                               expected_increase=expected_increase)
                    return True
                
                time.sleep(1.0)
                
            except Exception as e:
                log_error(e, "waiting_for_indexing")
                break
        
        logger.warning("Indexing timeout", timeout=timeout, expected_increase=expected_increase)
        return False
    
    def _index_single_document(self, file_path: str, reindex: bool = False) -> IndexingResult:
        """Index a single document with comprehensive error handling"""
        start_time = time.time()
        doc_uid = None
        
        try:
            log_operation("indexing_document", file_path=file_path, reindex=reindex)
            
            # Determine document UID
            doc_uid = (doc_uid_for_path(file_path) if config.doc_id_hash_mode == "PATH" 
                      else doc_uid_for_content(file_path))
            
            # Check if already indexed
            if not reindex and self._sentinel_exists(doc_uid):
                logger.info("Document already indexed, skipping", 
                           file_path=file_path, doc_uid=doc_uid)
                return IndexingResult(
                    success=True, doc_id=doc_uid, source=file_path, 
                    chunks_created=0, duration=time.time() - start_time
                )
            
            # Delete existing if reindexing
            if reindex:
                self._delete_document(doc_uid)
            
            # Load document
            docs = load_one_local(file_path, config.user_agent)
            if not docs:
                raise ValueError(f"No content extracted from {file_path}")
            
            # Split into chunks
            chunks = self.splitter.split_documents(docs)
            if not chunks:
                raise ValueError(f"No chunks created from {file_path}")
            
            # Add metadata to chunks
            for chunk in chunks:
                chunk.metadata.update({
                    "source": file_path,
                    "doc_uid": doc_uid,
                    "chunk_start": chunk.metadata.get("start_index", 0),
                    "indexed_at": time.time(),
                    "version": "2.0"
                })
            
            # Generate chunk IDs
            chunk_ids = self._build_chunk_ids(doc_uid, (len(chunks) + 1)) # +1 for sentinel, mahmoud 16/09/2025
            
            # Upsert chunks
            with self._lock:  # Thread safety
                upserted = self.vector_store.add_documents(
                    documents=chunks, 
                    ids=chunk_ids, 
                    namespace=self.namespace
                )
            
            # Upsert sentinel
            self._upsert_sentinel(doc_uid, file_path, len(upserted))
            
            duration = time.time() - start_time
            log_performance("document_indexing", duration, 
                          file_path=file_path, chunks=len(upserted))
            
            return IndexingResult(
                success=True,
                doc_id=doc_uid,
                source=file_path,
                chunks_created=len(upserted),
                duration=duration
            )
            
        except Exception as e:
            duration = time.time() - start_time
            log_error(e, "indexing_document", file_path=file_path, doc_uid=doc_uid)
            
            return IndexingResult(
                success=False,
                doc_id=doc_uid or "unknown",
                source=file_path,
                chunks_created=0,
                error=str(e),
                duration=duration
            )
    
    def _delete_document(self, doc_uid: str):
        """Delete all chunks and sentinel for a document"""
        try:
            # Delete chunks
            self.index.delete(
                namespace=self.namespace,
                filter={"doc_uid": doc_uid}
            )
            
            # Delete sentinel
            self.index.delete(
                namespace=self.namespace,
                ids=[self._sentinel_id(doc_uid)]
            )
            
            logger.info("Document deleted", doc_uid=doc_uid)
            
        except Exception as e:
            log_error(e, "deleting_document", doc_uid=doc_uid)
            raise
    
    def index_paths(self, paths: List[str], wipe: bool = False, reindex: bool = False, 
                   max_workers: int = 4) -> IndexingStats:
        """Index multiple paths with parallel processing"""
        start_time = time.time()
        log_operation("bulk_indexing", paths=paths, wipe=wipe, reindex=reindex)
        
        # Find all files
        files = iter_files(paths)
        if not files:
            logger.warning("No supported files found", paths=paths)
            return IndexingStats(0, 0, 0, 0, 0, 0, ["No supported files found"])
        
        logger.info("Found files to index", count=len(files))
        
        # Clear namespace if requested
        if wipe:
            try:
                self.index.delete(namespace=self.namespace, delete_all=True)
                logger.info("Namespace cleared", namespace=self.namespace)
            except NotFoundException:
                logger.info("Namespace not found for clearing", namespace=self.namespace)
        
        # Process files in parallel
        stats = IndexingStats(
            total_files=len(files),
            successful=0,
            failed=0,
            skipped=0,
            total_chunks=0,
            duration=0,
            errors=[]
        )
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_file = {
                executor.submit(self._index_single_document, file_path, reindex): file_path
                for file_path in files
            }
            
            # Process results as they complete
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    result = future.result()
                    
                    if result.success:
                        if result.chunks_created > 0:
                            stats.successful += 1
                            stats.total_chunks += result.chunks_created
                            logger.info("Document indexed successfully", 
                                      file_path=file_path, chunks=result.chunks_created)
                        else:
                            stats.skipped += 1
                            logger.info("Document skipped (already indexed)", 
                                      file_path=file_path)
                    else:
                        stats.failed += 1
                        stats.errors.append(f"{file_path}: {result.error}")
                        logger.error("Document indexing failed", 
                                   file_path=file_path, error=result.error)
                        
                except Exception as e:
                    stats.failed += 1
                    stats.errors.append(f"{file_path}: {str(e)}")
                    log_error(e, "processing_file", file_path=file_path)
        
        # Wait for indexing to complete
        if stats.total_chunks > 0:
            self._wait_for_indexing(stats.total_chunks + stats.successful)  # +1 for each sentinel
        
        stats.duration = time.time() - start_time
        
        log_performance("bulk_indexing", stats.duration,
                      total_files=stats.total_files,
                      successful=stats.successful,
                      failed=stats.failed,
                      total_chunks=stats.total_chunks)
        
        return stats
    
    def get_namespace_stats(self) -> Dict[str, Any]:
        """Get statistics for the current namespace"""
        try:
            stats = self.index.describe_index_stats()
            namespace_stats = stats.get("namespaces", {}).get(self.namespace, {})
            
            return {
                "namespace": self.namespace,
                "vector_count": namespace_stats.get("vectorCount", 0),
                "index_dimension": stats.get("dimension", 0),
                "index_metric": stats.get("metric", "unknown"),
                "total_index_vectors": stats.get("totalVectorCount", 0)
            }
            
        except Exception as e:
            log_error(e, "getting_namespace_stats")
            return {"error": str(e)}
    
    def list_documents(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List all documents in the namespace"""
        try:
            # Query for sentinel vectors
            result = self.index.query(
                namespace=self.namespace,
                vector=[0.0] * 768,  # Dummy vector
                filter={"kind": "sentinel"},
                top_k=limit,
                include_metadata=True
            )
            
            documents = []
            for match in result.matches:
                metadata = match.metadata
                documents.append({
                    "doc_uid": metadata.get("doc_uid"),
                    "source": metadata.get("source"),
                    "chunk_count": metadata.get("chunk_count"),
                    "indexed_at": metadata.get("indexed_at"),
                    "version": metadata.get("version", "1.0")
                })
            
            return documents
            
        except Exception as e:
            log_error(e, "listing_documents")
            return []

    def get_document_chunks(self, doc_uid: str, limit: int = 10000) -> List[Dict[str, Any]]:
        """Fetch all chunks' metadata for a given document UID from Pinecone.

        Returns a list of dicts with at least: {"text": str, "chunk_start": int}.
        """
        try:
            # Query all vectors for this document (non-sentinel)
            result = self.index.query(
                namespace=self.namespace,
                vector=[0.0] * 768,
                filter={"doc_uid": doc_uid},
                top_k=limit,
                include_metadata=True
            )

            chunks: List[Dict[str, Any]] = []
            for match in result.matches or []:
                md = match.metadata or {}
                # Common LangChain Pinecone store uses 'text' to store page_content
                text = md.get("text") or md.get("content") or ""
                chunk_start = md.get("chunk_start") or md.get("start_index") or 0
                # Skip sentinel if any slipped in
                if md.get("kind") == "sentinel":
                    continue
                if text:
                    chunks.append({
                        "text": text,
                        "chunk_start": chunk_start
                    })

            # Sort by chunk_start to preserve original document order
            chunks.sort(key=lambda c: c.get("chunk_start", 0))
            return chunks
        except Exception as e:
            log_error(e, "getting_document_chunks", doc_uid=doc_uid)
            return []

# Backward compatibility functions
def index_paths(paths: List[str], namespace: str = None, wipe: bool = False, reindex: bool = False):
    """Backward compatible function"""
    indexer = EnhancedIndexer(namespace)
    stats = indexer.index_paths(paths, wipe, reindex)
    
    if stats.failed > 0:
        logger.warning("Some documents failed to index", 
                      failed=stats.failed, errors=stats.errors)
    
    return stats

# Export
__all__ = ['EnhancedIndexer', 'IndexingResult', 'IndexingStats', 'index_paths']
