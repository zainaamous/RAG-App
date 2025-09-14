"""
Enhanced Query Engine for RAG System
Improved retrieval, response formatting, and query analysis
"""
import time
from typing import TypedDict, List, Dict, Any, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum

from langchain.chat_models import init_chat_model
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain import hub
from pinecone import Pinecone
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage

from config import config
from logger import logger, log_operation, log_performance, log_error

class QueryType(Enum):
    """Types of queries for better handling"""
    FACTUAL = "factual"
    ANALYTICAL = "analytical"
    COMPARATIVE = "comparative"
    SUMMARIZATION = "summarization"
    CREATIVE = "creative"

@dataclass
class QueryResult:
    """Enhanced query result with metadata"""
    answer: str
    sources: List[Dict[str, Any]]
    query_type: QueryType
    confidence: float
    processing_time: float
    total_chunks_retrieved: int
    relevant_chunks_used: int
    metadata: Dict[str, Any]

@dataclass
class RetrievalStats:
    """Statistics for retrieval process"""
    total_candidates: int
    documents_found: int
    chunks_per_doc: int
    similarity_scores: List[float]
    retrieval_time: float

class QueryAnalyzer:
    """Analyzes queries to determine type and optimal retrieval strategy"""
    
    def __init__(self):
        self.type_keywords = {
            QueryType.FACTUAL: ["what", "when", "where", "who", "how", "which", "define", "meaning"],
            QueryType.ANALYTICAL: ["analyze", "explain", "why", "cause", "effect", "relationship", "impact"],
            QueryType.COMPARATIVE: ["compare", "difference", "versus", "vs", "contrast", "similar", "better"],
            QueryType.SUMMARIZATION: ["summary", "summarize", "overview", "brief", "main points", "key points"],
            QueryType.CREATIVE: ["create", "generate", "write", "design", "suggest", "recommend", "ideas"]
        }
    
    def analyze_query(self, query: str) -> Tuple[QueryType, Dict[str, Any]]:
        """Analyze query to determine type and characteristics"""
        query_lower = query.lower()
        
        # Determine query type
        query_type = QueryType.FACTUAL  # Default
        max_matches = 0
        
        for qtype, keywords in self.type_keywords.items():
            matches = sum(1 for keyword in keywords if keyword in query_lower)
            if matches > max_matches:
                max_matches = matches
                query_type = qtype
        
        # Analyze query characteristics
        metadata = {
            "length": len(query.split()),
            "has_question_mark": "?" in query,
            "has_numbers": any(char.isdigit() for char in query),
            "keywords": [word for word in query_lower.split() if len(word) > 3],
            "complexity": "high" if len(query.split()) > 10 else "medium" if len(query.split()) > 5 else "low"
        }
        
        return query_type, metadata

class EnhancedQueryEngine:
    """Enhanced query engine with improved retrieval and response generation"""
    
    def __init__(self, namespace: str = None):
        self.namespace = namespace or config.rag_namespace
        self.llm = None
        self.embedder = None
        self.vector_store = None
        self.query_analyzer = QueryAnalyzer()
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize all components"""
        try:
            log_operation("initializing_query_engine", namespace=self.namespace)
            
            # Initialize LLM
            self.llm = init_chat_model(
                config.llm.model, 
                model_provider=config.llm.provider,
                temperature=config.llm.temperature,
                max_tokens=config.llm.max_tokens
            )
            
            # Initialize embeddings
            self.embedder = GoogleGenerativeAIEmbeddings(model=config.embedding.model)
            
            # Initialize Pinecone
            pc = Pinecone(api_key=config.pinecone_api_key)
            index = pc.Index(config.pinecone.index_name)
            
            # Initialize vector store
            self.vector_store = PineconeVectorStore(embedding=self.embedder, index=index)
            
            logger.info("Query engine components initialized successfully")
            
        except Exception as e:
            log_error(e, "initializing_query_engine")
            raise
    
    def _retrieve_context(self, query: str, query_type: QueryType, 
                         query_metadata: Dict[str, Any]) -> Tuple[List[Document], RetrievalStats]:
        """Enhanced context retrieval with query-type optimization"""
        start_time = time.time()
        
        try:
            # Adjust retrieval parameters based on query type
            if query_type == QueryType.FACTUAL:
                # For factual queries, get more specific chunks
                pool_k = config.retrieval.pool_k
                fetch_k = config.retrieval.pool_fetch_k
            elif query_type == QueryType.ANALYTICAL:
                # For analytical queries, get broader context
                pool_k = int(config.retrieval.pool_k * 1.5)
                fetch_k = int(config.retrieval.pool_fetch_k * 1.5)
            elif query_type == QueryType.SUMMARIZATION:
                # For summarization, get more diverse content
                pool_k = config.retrieval.pool_k
                fetch_k = config.retrieval.pool_fetch_k
            else:
                # Default parameters
                pool_k = config.retrieval.pool_k
                fetch_k = config.retrieval.pool_fetch_k
            
            # Perform similarity search
            hits = self.vector_store.similarity_search_with_score(
                query,
                k=pool_k,
                namespace=self.namespace,
                search_type="mmr",
                fetch_k=fetch_k
            )
            
            if not hits:
                logger.warning("No documents found for query", query=query)
                return [], RetrievalStats(0, 0, 0, [], time.time() - start_time)
            
            # Group by document and rank
            by_doc = defaultdict(list)
            for doc, score in hits:
                doc_uid = doc.metadata.get("doc_uid", "unknown")
                by_doc[doc_uid].append((doc, score))
            
            # Rank documents by best score
            ranked_docs = sorted(by_doc.items(), key=lambda kv: min(s for _, s in kv[1]))[:config.retrieval.max_docs]
            
            # Select best chunks per document
            chosen_docs = []
            similarity_scores = []
            
            for doc_uid, doc_chunks in ranked_docs:
                # Sort chunks by score and take best ones
                top_chunks = sorted(doc_chunks, key=lambda x: x[1])[:config.retrieval.k_per_doc]
                
                for doc, score in top_chunks:
                    chosen_docs.append(doc)
                    similarity_scores.append(score)
            
            # Filter by similarity threshold
            filtered_docs = []
            for doc, score in zip(chosen_docs, similarity_scores):
                if score >= config.retrieval.similarity_threshold:
                    filtered_docs.append(doc)
            
            retrieval_time = time.time() - start_time
            
            stats = RetrievalStats(
                total_candidates=len(hits),
                documents_found=len(by_doc),
                chunks_per_doc=config.retrieval.k_per_doc,
                similarity_scores=similarity_scores,
                retrieval_time=retrieval_time
            )
            
            log_performance("context_retrieval", retrieval_time,
                          query_type=query_type.value,
                          total_candidates=stats.total_candidates,
                          documents_found=stats.documents_found,
                          final_chunks=len(filtered_docs))
            
            return filtered_docs, stats
            
        except Exception as e:
            log_error(e, "retrieving_context", query=query)
            return [], RetrievalStats(0, 0, 0, [], time.time() - start_time)
    
    def _generate_answer(self, query: str, context_docs: List[Document], 
                        query_type: QueryType, query_metadata: Dict[str, Any]) -> str:
        """Generate answer with query-type specific prompting"""
        try:
            # Create context content
            context_content = "\n\n".join([
                f"[Source: {doc.metadata.get('source', 'unknown')}]\n{doc.page_content}"
                for doc in context_docs
            ])
            
            # Create query-type specific system prompt
            system_prompts = {
                QueryType.FACTUAL: "You are a factual information assistant. Provide accurate, concise answers based on the provided context.",
                QueryType.ANALYTICAL: "You are an analytical assistant. Analyze the provided context to explain relationships, causes, and effects.",
                QueryType.COMPARATIVE: "You are a comparison assistant. Compare and contrast information from the provided context.",
                QueryType.SUMMARIZATION: "You are a summarization assistant. Create clear, comprehensive summaries from the provided context.",
                QueryType.CREATIVE: "You are a creative assistant. Use the provided context to generate creative and innovative responses."
            }
            
            system_prompt = system_prompts.get(query_type, system_prompts[QueryType.FACTUAL])
            
            # Create enhanced prompt
            if query_type == QueryType.SUMMARIZATION:
                prompt = f"""Based on the following context, provide a comprehensive summary that addresses: {query}

Context:
{context_content}

Please provide a well-structured summary that covers the key points and main themes."""
            
            elif query_type == QueryType.ANALYTICAL:
                prompt = f"""Analyze the following context to answer: {query}

Context:
{context_content}

Please provide a detailed analysis that explains the relationships, causes, effects, and implications."""
            
            else:
                # Default prompt
                prompt = f"""Context:
{context_content}

Question: {query}

Please provide a helpful and accurate answer based on the context provided."""
            
            # Generate response
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ]
            
            response = self.llm.invoke(messages)
            return response.content
            
        except Exception as e:
            log_error(e, "generating_answer", query=query)
            return f"I apologize, but I encountered an error while processing your query: {str(e)}"
    
    def _calculate_confidence(self, similarity_scores: List[float], 
                            context_docs: List[Document]) -> float:
        """Calculate confidence score based on similarity and context quality"""
        if not similarity_scores:
            return 0.0
        
        # Base confidence on average similarity score
        avg_similarity = sum(similarity_scores) / len(similarity_scores)
        
        # Adjust based on context quality
        context_quality = min(len(context_docs) / config.retrieval.max_docs, 1.0)
        
        # Combine metrics
        confidence = (avg_similarity * 0.7) + (context_quality * 0.3)
        
        return min(max(confidence, 0.0), 1.0)
    
    def query(self, question: str) -> QueryResult:
        """Main query method with enhanced processing"""
        start_time = time.time()
        
        try:
            log_operation("processing_query", question=question)
            
            # Analyze query
            query_type, query_metadata = self.query_analyzer.analyze_query(question)
            
            # Retrieve context
            context_docs, retrieval_stats = self._retrieve_context(
                question, query_type, query_metadata
            )
            
            if not context_docs:
                return QueryResult(
                    answer="I couldn't find relevant information to answer your question. Please try rephrasing or check if the documents contain information about this topic.",
                    sources=[],
                    query_type=query_type,
                    confidence=0.0,
                    processing_time=time.time() - start_time,
                    total_chunks_retrieved=0,
                    relevant_chunks_used=0,
                    metadata={"retrieval_stats": retrieval_stats}
                )
            
            # Generate answer
            answer = self._generate_answer(question, context_docs, query_type, query_metadata)
            
            # Prepare sources
            sources = []
            for doc in context_docs:
                sources.append({
                    "source": doc.metadata.get("source", "unknown"),
                    "chunk_start": doc.metadata.get("chunk_start", 0),
                    "doc_uid": doc.metadata.get("doc_uid", "unknown"),
                    "content_preview": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
                })
            
            # Calculate confidence
            confidence = self._calculate_confidence(retrieval_stats.similarity_scores, context_docs)
            
            processing_time = time.time() - start_time
            
            result = QueryResult(
                answer=answer,
                sources=sources,
                query_type=query_type,
                confidence=confidence,
                processing_time=processing_time,
                total_chunks_retrieved=retrieval_stats.total_candidates,
                relevant_chunks_used=len(context_docs),
                metadata={
                    "retrieval_stats": retrieval_stats,
                    "query_metadata": query_metadata
                }
            )
            
            log_performance("query_processing", processing_time,
                          query_type=query_type.value,
                          confidence=confidence,
                          sources_used=len(sources))
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            log_error(e, "processing_query", question=question)
            
            return QueryResult(
                answer=f"I encountered an error while processing your query: {str(e)}",
                sources=[],
                query_type=QueryType.FACTUAL,
                confidence=0.0,
                processing_time=processing_time,
                total_chunks_retrieved=0,
                relevant_chunks_used=0,
                metadata={"error": str(e)}
            )
    
    def get_query_stats(self) -> Dict[str, Any]:
        """Get query engine statistics"""
        try:
            # Get namespace stats
            pc = Pinecone(api_key=config.pinecone_api_key)
            index = pc.Index(config.pinecone.index_name)
            stats = index.describe_index_stats()
            
            namespace_stats = stats.get("namespaces", {}).get(self.namespace, {})
            
            return {
                "namespace": self.namespace,
                "total_vectors": namespace_stats.get("vectorCount", 0),
                "index_dimension": stats.get("dimension", 0),
                "retrieval_config": {
                    "max_docs": config.retrieval.max_docs,
                    "k_per_doc": config.retrieval.k_per_doc,
                    "similarity_threshold": config.retrieval.similarity_threshold
                }
            }
            
        except Exception as e:
            log_error(e, "getting_query_stats")
            return {"error": str(e)}

# Backward compatibility
def build_pipeline(namespace: str = None, **kwargs):
    """Backward compatible function"""
    engine = EnhancedQueryEngine(namespace)
    
    def retrieve(state):
        result = engine.query(state["question"])
        return {"context": [Document(page_content=doc["content_preview"], metadata=doc) for doc in result.sources]}
    
    def generate(state):
        # For backward compatibility, just return the answer
        result = engine.query(state["question"])
        return {"answer": result.answer}
    
    return retrieve, generate

# Export
__all__ = ['EnhancedQueryEngine', 'QueryResult', 'QueryType', 'build_pipeline']
