# Conversation-Aware RAG System

This document describes the enhanced RAG system with conversation memory and context management.

## Overview

The conversation-aware RAG system transforms the traditional RAG flow from:

**Old Flow:**
```
User Query → Retrieve Docs → LLM Answer
```

**New Flow:**
```
User Query → Fetch conversation history → Build context (history + docs) → LLM Answer
```

## Key Features

### 1. Conversation Memory
- **Persistent Storage**: Conversations are stored in SQLite database
- **Message History**: Full conversation history with timestamps and metadata
- **Conversation IDs**: Each conversation has a unique identifier

### 2. Context Building
- **History Integration**: Recent conversation history is included in LLM context
- **Smart Truncation**: History is truncated to fit within token limits
- **Summary Support**: Long conversations can be summarized for memory efficiency

### 3. Memory Management
- **Automatic Summarization**: Conversations are summarized when they exceed threshold
- **Selective Memory**: Only conversations within the same conversation_id are considered
- **Cleanup**: Old conversations can be automatically cleaned up

## Architecture

### Core Components

1. **ConversationManager** (`conversation_manager.py`)
   - Manages conversation storage and retrieval
   - Handles message persistence
   - Provides conversation summarization

2. **EnhancedQueryEngine** (`query_engine.py`)
   - Extended with conversation awareness
   - New `answer_question()` method for complete conversation flow
   - Context building with conversation history

3. **API Endpoints** (`api_v2.py`, `dashboard_server.py`)
   - Conversation management endpoints
   - Enhanced query endpoints with conversation support

## Usage Examples

### Basic Conversation Flow

```python
from query_engine import EnhancedQueryEngine
from conversation_manager import conversation_manager

# Initialize engine
engine = EnhancedQueryEngine()

# Create conversation
conversation_id = conversation_manager.create_conversation(
    title="My Discussion",
    metadata={"topic": "AI"}
)

# Ask questions with conversation context
result1 = engine.answer_question("What is machine learning?", conversation_id)
result2 = engine.answer_question("Can you give me an example?", conversation_id)
result3 = engine.answer_question("How does that work?", conversation_id)
```

### API Usage

#### Create Conversation
```bash
curl -X POST "http://localhost:8000/conversations" \
  -H "Content-Type: application/json" \
  -d '{"title": "My Chat", "metadata": {"topic": "AI"}}'
```

#### Query with Conversation
```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is AI?",
    "conversation_id": "your-conversation-id"
  }'
```

#### Get Conversation History
```bash
curl "http://localhost:8000/conversations/your-conversation-id"
```

## API Endpoints

### Conversation Management

- `POST /conversations` - Create new conversation
- `GET /conversations` - List conversations
- `GET /conversations/{id}` - Get conversation history
- `DELETE /conversations/{id}` - Delete conversation
- `POST /conversations/{id}/summarize` - Manually summarize conversation
- `POST /conversations/cleanup` - Clean up old conversations

### Enhanced Query

- `POST /query` - Query with optional conversation_id
- `POST /query/stream` - Streaming query with conversation support

## Configuration

### Conversation Settings

```python
# In conversation_manager.py
SUMMARY_THRESHOLD = 10  # Messages before summarization
MAX_HISTORY_TOKENS = 2000  # Max tokens for history context
MAX_HISTORY_MESSAGES = 10  # Max messages to load
```

### Database

The system uses SQLite for conversation storage:
- `conversations.db` - Main database file
- Tables: `conversations`, `messages`, `conversation_summaries`

## Memory Management

### Automatic Summarization

When a conversation exceeds the threshold (default: 10 messages), it's automatically summarized:

1. Recent messages are summarized into a concise summary
2. Summary is stored separately
3. Only summary + recent messages are used for context
4. Saves tokens and maintains context quality

### Manual Memory Control

```python
# Create new conversation (forgets previous context)
new_conversation_id = conversation_manager.create_conversation()

# Get conversation summary
summary = conversation_manager.get_conversation_summary(conversation_id)

# Clean up old conversations
deleted_count = conversation_manager.cleanup_old_conversations(days_old=30)
```

## Testing

Run the test suite to verify functionality:

```bash
python test_conversation_rag.py
```

This will test:
- Basic conversation flow
- Conversation summarization
- API compatibility
- Memory management

## Example Scripts

- `conversation_example.py` - Simple usage example
- `test_conversation_rag.py` - Comprehensive test suite

## Benefits

### 1. Contextual Understanding
- LLM can reference previous questions and answers
- Maintains conversation thread continuity
- Better follow-up question handling

### 2. Memory Efficiency
- Automatic summarization prevents context overflow
- Selective memory (only within conversation)
- Configurable memory limits

### 3. User Experience
- Natural conversation flow
- Persistent chat history
- Conversation management (create, delete, list)

### 4. Scalability
- SQLite storage for conversations
- Efficient querying and indexing
- Automatic cleanup of old conversations

## Migration from Old System

The new system is backward compatible:

```python
# Old way (still works)
result = engine.query("What is AI?")

# New way (with conversation)
result = engine.answer_question("What is AI?", conversation_id)
```

## Performance Considerations

- **Token Usage**: Conversation history increases token usage
- **Database I/O**: SQLite operations add minimal overhead
- **Memory**: Summarization keeps memory usage bounded
- **Latency**: Context building adds ~10-50ms per query

## Future Enhancements

1. **Vector-based Memory**: Use embeddings for semantic conversation search
2. **Multi-user Support**: User-specific conversation isolation
3. **Advanced Summarization**: Topic-based conversation segmentation
4. **Real-time Sync**: WebSocket support for live conversations
5. **Export/Import**: Conversation backup and restore functionality
