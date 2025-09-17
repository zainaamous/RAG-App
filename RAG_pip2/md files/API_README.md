# RAG Knowledge Base API

A FastAPI-based REST API for ingesting documents and querying your RAG knowledge base.

## Features

- **Document Ingestion**: Upload text content or files to the knowledge base
- **Query Interface**: Ask questions and get answers with source citations
- **Document Management**: List, view info, and delete documents
- **Namespace Support**: Organize documents in different namespaces
- **Health Monitoring**: Check API status and vector counts

## Installation

1. Install API dependencies:
```bash
pip install -r requirements_api.txt
```

2. Make sure your environment variables are set (`.env` file or environment):
```
GOOGLE_API_KEY=your_google_api_key
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX=your_index_name
RAG_NAMESPACE=library-global
```

## Running the API

### Option 1: Using the startup script
```bash
python start_api.py
```

### Option 2: Using uvicorn directly
```bash
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### Health Check
- `GET /health` - Check API status and namespace statistics

### Document Ingestion
- `POST /ingest` - Ingest text content directly
- `POST /ingest/file` - Upload and ingest a file

### Querying
- `POST /query` - Query the knowledge base

### Document Management
- `GET /documents` - List all documents in namespace
- `GET /documents/{doc_id}` - Get document information
- `DELETE /documents/{doc_id}` - Delete a document
- `POST /reindex/{doc_id}` - Reindex a document (not fully implemented)

## Example Usage

### Ingest a document
```bash
curl -X POST "http://localhost:8000/ingest" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "This is a sample document about machine learning...",
    "namespace": "library-global",
    "source": "manual_input"
  }'
```

### Query the knowledge base
```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is machine learning?",
    "namespace": "library-global"
  }'
```

### Upload a file
```bash
curl -X POST "http://localhost:8000/ingest/file" \
  -F "file=@document.pdf" \
  -F "namespace=library-global"
```

## Configuration

The API uses the same configuration as your existing RAG system:
- Chunk size and overlap settings from `config.py`
- Same embedding model and vector store
- Compatible with your existing document processing pipeline

## Error Handling

The API includes comprehensive error handling:
- Validation errors for malformed requests
- File processing errors
- Vector store connection issues
- Document not found errors

All errors return JSON responses with appropriate HTTP status codes.
