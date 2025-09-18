# 🚀 Enhanced RAG System - Production Ready

<div align="center">

![Enhanced RAG System](https://img.shields.io/badge/Enhanced-RAG%20System-blue?style=for-the-badge&logo=python)
![Version](https://img.shields.io/badge/Version-2.0.0-green?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Production%20Ready-success?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.8+-blue?style=for-the-badge&logo=python)

**🎯 Conversation-Aware RAG System with Advanced Features**

[Features](#-features) • [Quick Start](#-quick-start) • [API Documentation](#-api-documentation) • [Dashboard](#-dashboard) • [Monitoring](#-monitoring)

</div>

---

## ✨ Features

### 🧠 **Conversation-Aware RAG**
- **Memory Management**: Persistent conversation history with SQLite
- **Context Building**: Intelligent context assembly from conversation history
- **Smart Summarization**: Automatic conversation summarization to save tokens
- **Selective Memory**: Conversation-specific context isolation

### 🚀 **Production-Ready APIs**
- **FastAPI v2**: High-performance async API with automatic documentation
- **Rate Limiting**: Built-in protection against abuse (100 req/min per IP)
- **Input Validation**: Comprehensive request validation with Pydantic
- **Error Handling**: Graceful error handling with detailed logging

### 📊 **Real-Time Monitoring**
- **System Metrics**: CPU, memory, disk usage monitoring
- **Performance Tracking**: Request/response time monitoring
- **Health Checks**: Component-level health monitoring
- **Error Tracking**: Comprehensive error logging and tracking

### 🎨 **Beautiful Dashboard**
- **Modern UI**: Clean, responsive web interface
- **Real-Time Updates**: Live conversation and system status
- **File Management**: Easy document upload and management
- **Conversation History**: Visual conversation management

### 🔧 **Advanced Features**
- **Query Analysis**: Intelligent query type detection and optimization
- **Caching**: LRU caching for improved performance
- **Connection Pooling**: Optimized database connections
- **Retry Logic**: Automatic retry with exponential backoff

---

## 🚀 Quick Start

### 1. **Beautiful System Launcher**
```bash
# One-click system management
python launch.py
```

### 2. **System Initialization**
```bash
# Check system health and configuration
python start_system.py
```

### 3. **Start Services**
```bash
# Start API server
python start_api.py

# Start dashboard (in another terminal)
python dashboard_server.py
```

### 4. **System Status**
```bash
# Check system status
python system_status.py

# Watch mode (refresh every 30s)
python system_status.py --watch
```

---

## 📡 API Documentation

### **Base URL**: `http://localhost:8000`

### **Key Endpoints**

#### 🏥 **Health & Monitoring**
```http
GET /health          # System health check
GET /metrics         # Performance metrics
GET /stats           # System statistics
```

#### 💬 **Conversation Management**
```http
POST /conversations                    # Create conversation
GET  /conversations                    # List conversations
GET  /conversations/{id}               # Get conversation history
DELETE /conversations/{id}             # Delete conversation
POST /conversations/{id}/summarize     # Summarize conversation
```

#### 🔍 **Query Processing**
```http
POST /query                           # Single query
POST /query/stream                    # Streaming query
POST /query/batch                     # Batch queries
```

#### 📄 **Document Management**
```http
POST /ingest                          # Upload document
GET  /documents                       # List documents
DELETE /documents/{id}                # Delete document
```

### **Interactive API Docs**
Visit: **http://localhost:8000/docs**

---

## 🎨 Dashboard

### **Access**: http://localhost:8080

### **Features**
- 📊 **System Overview**: Real-time system status and metrics
- 💬 **Conversation Interface**: Chat with conversation memory
- 📁 **Document Management**: Upload, view, and manage documents
- 🔍 **Query Interface**: Advanced query options and settings
- 📈 **Analytics**: Performance metrics and usage statistics

---

## 📊 Monitoring

### **System Metrics**
- **CPU Usage**: Real-time CPU monitoring
- **Memory Usage**: Memory consumption tracking
- **Disk Usage**: Storage utilization monitoring
- **Request Metrics**: Response times, error rates, throughput

### **Health Checks**
- **Overall Status**: System-wide health assessment
- **Component Health**: Individual service health
- **Performance Metrics**: Historical performance data

### **Monitoring Tools**
```bash
# Real-time status
python system_status.py

# System tests
python system_test.py

# Configuration check
python start_system.py
```

---

## 🔧 Configuration

### **Environment Variables**
```bash
# Required
PINECONE_API_KEY=your_pinecone_key
GOOGLE_API_KEY=your_google_key
PINECONE_INDEX_NAME=your_index_name
RAG_NAMESPACE=your_namespace

# Optional
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
EMBEDDING_MODEL=models/text-embedding-004
LLM_MODEL=gemini-2.5-flash
```

### **Configuration Files**
- `config.py` - Main configuration management
- `.env` - Environment variables
- `requirements_full.txt` - Dependencies

---

## 🧪 Testing

### **System Tests**
```bash
# Run comprehensive test suite
python system_test.py
```

### **Test Categories**
1. ✅ Configuration Testing
2. ✅ Logging System Testing
3. ✅ File System Testing
4. ✅ Conversation Management Testing
5. ✅ System Monitoring Testing
6. ✅ Query Engine Testing
7. ✅ API Models Testing
8. ✅ Integration Testing
9. ✅ Performance Testing

---

## 📚 Documentation

### **Available Documentation**
- 📖 **API Documentation**: `API_README.md`
- 🏗️ **System Architecture**: `API_Architecture.md`
- ✨ **Enhanced Features**: `ENHANCED_README.md`
- 💬 **Conversation RAG**: `CONVERSATION_RAG_README.md`
- 🧹 **Project Cleanup**: `PROJECT_CLEANUP_ANALYSIS.md`
- 🚀 **System Enhancement**: `SYSTEM_ENHANCEMENT_SUMMARY.md`

---

## 🎯 Usage Examples

### **Basic Query**
```python
import requests

response = requests.post("http://localhost:8000/query", json={
    "question": "What is machine learning?",
    "namespace": "default"
})

print(response.json())
```

### **Conversation-Aware Query**
```python
# Create conversation
conv_response = requests.post("http://localhost:8000/conversations", json={
    "title": "ML Discussion"
})
conversation_id = conv_response.json()["conversation_id"]

# Ask questions with context
response = requests.post("http://localhost:8000/query", json={
    "question": "What are the types of machine learning?",
    "conversation_id": conversation_id
})

print(response.json())
```

### **Streaming Query**
```python
response = requests.post("http://localhost:8000/query/stream", json={
    "question": "Explain deep learning",
    "stream": True
}, stream=True)

for chunk in response.iter_content(chunk_size=1024):
    if chunk:
        print(chunk.decode())
```

---

## 🔒 Security Features

### **Input Validation**
- Pydantic validators for all API inputs
- XSS protection for user inputs
- Length and format validation
- SQL injection prevention

### **Rate Limiting**
- IP-based request limiting (100 req/min)
- Automatic cleanup of old requests
- Graceful HTTP 429 responses

### **Error Handling**
- Comprehensive error logging
- Safe error message sanitization
- Graceful degradation

---

## 📈 Performance

### **Optimizations**
- **Query Caching**: LRU cache for repeated queries
- **Connection Pooling**: Reused database connections
- **Database Optimization**: WAL mode and optimized settings
- **Async Processing**: Non-blocking I/O operations

### **Monitoring**
- Real-time performance metrics
- Historical performance tracking
- Component health monitoring
- Error rate tracking

---

## 🛠️ Development

### **Project Structure**
```
RAG_pip2/
├── 🚀 launch.py                 # Beautiful system launcher
├── 🎯 start_system.py           # System initialization
├── 📊 system_status.py          # Status monitoring
├── 🧪 system_test.py            # Test suite
├── 📡 api_v2.py                 # Enhanced API
├── 🎨 dashboard_server.py       # Dashboard server
├── 🧠 query_engine.py           # Query processing
├── 💬 conversation_manager.py   # Conversation management
├── 📊 system_monitor.py         # System monitoring
├── ⚙️ config.py                 # Configuration
└── 📚 docs/                     # Documentation
```

### **Dependencies**
```bash
# Core dependencies
pip install fastapi uvicorn langchain pinecone-client

# Optional monitoring
pip install psutil aiosqlite

# Development
pip install pytest httpx
```

---

## 🎉 What's New in v2.0

### **🚀 Major Enhancements**
- ✅ **Conversation-Aware RAG** with memory management
- ✅ **Real-Time System Monitoring** with health checks
- ✅ **Production-Ready APIs** with rate limiting
- ✅ **Beautiful Dashboard** with modern UI
- ✅ **Comprehensive Testing** with automated test suite
- ✅ **Advanced Security** with input validation
- ✅ **Performance Optimization** with caching and pooling

### **🔧 Technical Improvements**
- ✅ Enhanced error handling and recovery
- ✅ Database connection optimization
- ✅ Query analysis caching
- ✅ Component health monitoring
- ✅ Request/response monitoring
- ✅ Graceful degradation

---

## 🤝 Support

### **Getting Help**
1. 📖 Check the documentation in the `docs/` folder
2. 🧪 Run `python system_test.py` to verify system health
3. 📊 Use `python system_status.py` to check system status
4. 🔧 Run `python start_system.py` for configuration check

### **System Health**
```bash
# Quick health check
curl http://localhost:8000/health

# Detailed status
python system_status.py

# Full system test
python system_test.py
```

---

## 🎯 Ready to Use!

Your Enhanced RAG System is now **production-ready** with:

- 🧠 **Conversation-aware AI** with memory management
- 📊 **Real-time monitoring** and health checks
- 🚀 **High-performance APIs** with rate limiting
- 🎨 **Beautiful dashboard** for easy interaction
- 🔒 **Enterprise-grade security** and validation
- 📈 **Comprehensive testing** and monitoring

**Start your system with:**
```bash
python launch.py
```

**Happy querying! 🚀**
