# API Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Client App    │    │   File Upload   │    │  Text Content   │
│                 │    │                 │    │                 │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────▼─────────────┐
                    │       FastAPI Server      │
                    │                           │
                    │  ┌─────────────────────┐  │
                    │  │   /ingest           │  │
                    │  │   /ingest/file      │  │
                    │  │   /query            │  │
                    │  │   /documents        │  │
                    │  │   /health           │  │
                    │  └─────────────────────┘  │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │    Your Existing RAG      │
                    │        System             │
                    │                           │
                    │  ┌─────────────────────┐  │
                    │  │   index_fs.py       │  │
                    │  │   query.py          │  │
                    │  │   filesys.py        │  │
                    │  │   config.py         │  │
                    │  └─────────────────────┘  │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │      Pinecone Vector      │
                    │         Database          │
                    └───────────────────────────┘
```

## Data Flow:

1. **Ingestion Flow:**
   Client → API → Temp File → filesys.py → index_fs.py → Pinecone

2. **Query Flow:**
   Client → API → query.py → Pinecone → LLM → Response

3. **Management Flow:**
   Client → API → Pinecone Direct → CRUD Operations
