"""
Conversation Manager for RAG System
Handles conversation history, memory management, and context building
"""
import json
import sqlite3
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

# Optional async SQLite support
try:
    import aiosqlite
    ASYNC_SQLITE_AVAILABLE = True
except ImportError:
    ASYNC_SQLITE_AVAILABLE = False

from logger import logger, log_operation, log_error

@dataclass
class ConversationMessage:
    """Represents a single message in a conversation"""
    message_id: str
    conversation_id: str
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class ConversationSummary:
    """Represents a conversation summary for memory management"""
    conversation_id: str
    summary_text: str
    message_count: int
    created_at: datetime
    last_updated: datetime

class ConversationManager:
    """Manages conversation history and memory for RAG system"""
    
    def __init__(self, db_path: str = "conversations.db", max_connections: int = 10):
        self.db_path = Path(db_path)
        self.max_connections = max_connections
        self._connection_pool = None
        self._async_available = ASYNC_SQLITE_AVAILABLE
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database for conversation storage"""
        try:
            with sqlite3.connect(self.db_path, timeout=30.0) as conn:
                # Enable WAL mode for better concurrency
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA cache_size=10000")
                conn.execute("PRAGMA temp_store=MEMORY")
                
                cursor = conn.cursor()
                
                # Create conversations table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        conversation_id TEXT PRIMARY KEY,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        title TEXT,
                        metadata TEXT
                    )
                """)
                
                # Create messages table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        message_id TEXT PRIMARY KEY,
                        conversation_id TEXT,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        metadata TEXT,
                        FOREIGN KEY (conversation_id) REFERENCES conversations (conversation_id)
                    )
                """)
                
                # Create conversation summaries table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS conversation_summaries (
                        conversation_id TEXT PRIMARY KEY,
                        summary_text TEXT NOT NULL,
                        message_count INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (conversation_id) REFERENCES conversations (conversation_id)
                    )
                """)
                
                # Create indexes for better performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_messages_conversation_id 
                    ON messages (conversation_id)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_messages_timestamp 
                    ON messages (timestamp)
                """)
                
                conn.commit()
                logger.info("Conversation database initialized successfully")
                
        except Exception as e:
            log_error(e, "initializing_conversation_database")
            raise
    
    def create_conversation(self, title: str = None, metadata: Dict[str, Any] = None) -> str:
        """Create a new conversation and return its ID"""
        try:
            conversation_id = str(uuid.uuid4())
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO conversations (conversation_id, title, metadata)
                    VALUES (?, ?, ?)
                """, (
                    conversation_id,
                    title or f"Conversation {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    json.dumps(metadata or {})
                ))
                
                conn.commit()
            
            log_operation("conversation_created", conversation_id=conversation_id)
            return conversation_id
            
        except Exception as e:
            log_error(e, "creating_conversation")
            raise
    
    def save_message(self, conversation_id: str, role: str, content: str, 
                    metadata: Dict[str, Any] = None) -> str:
        """Save a message to a conversation"""
        try:
            message_id = str(uuid.uuid4())
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO messages (message_id, conversation_id, role, content, metadata)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    message_id,
                    conversation_id,
                    role,
                    content,
                    json.dumps(metadata or {})
                ))
                
                # Update conversation last_updated
                cursor.execute("""
                    UPDATE conversations 
                    SET last_updated = CURRENT_TIMESTAMP 
                    WHERE conversation_id = ?
                """, (conversation_id,))
                
                conn.commit()
            
            log_operation("message_saved", 
                         conversation_id=conversation_id, 
                         message_id=message_id, 
                         role=role)
            return message_id
            
        except Exception as e:
            log_error(e, "saving_message", conversation_id=conversation_id)
            raise
    
    def load_conversation_history(self, conversation_id: str, limit: int = 10) -> List[ConversationMessage]:
        """Load recent conversation history"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT message_id, conversation_id, role, content, timestamp, metadata
                    FROM messages 
                    WHERE conversation_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (conversation_id, limit))
                
                messages = []
                for row in cursor.fetchall():
                    message = ConversationMessage(
                        message_id=row[0],
                        conversation_id=row[1],
                        role=row[2],
                        content=row[3],
                        timestamp=datetime.fromisoformat(row[4]),
                        metadata=json.loads(row[5]) if row[5] else {}
                    )
                    messages.append(message)
                
                # Return in chronological order (oldest first)
                messages.reverse()
                
                log_operation("conversation_history_loaded", 
                             conversation_id=conversation_id, 
                             message_count=len(messages))
                return messages
                
        except Exception as e:
            log_error(e, "loading_conversation_history", conversation_id=conversation_id)
            return []
    
    def format_conversation_history(self, messages: List[ConversationMessage], 
                                  max_tokens: int = 2000) -> str:
        """Format conversation history for LLM context"""
        if not messages:
            return ""
        
        formatted_history = []
        current_tokens = 0
        
        # Process messages in reverse order (newest first) to fit within token limit
        for message in reversed(messages):
            role_label = "User" if message.role == "user" else "Assistant"
            message_text = f"{role_label}: {message.content}"
            
            # Rough token estimation (4 characters per token)
            estimated_tokens = len(message_text) // 4
            
            if current_tokens + estimated_tokens > max_tokens:
                break
            
            formatted_history.insert(0, message_text)
            current_tokens += estimated_tokens
        
        return "\n\n".join(formatted_history)
    
    def get_conversation_summary(self, conversation_id: str) -> Optional[ConversationSummary]:
        """Get conversation summary if it exists"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT conversation_id, summary_text, message_count, created_at, last_updated
                    FROM conversation_summaries
                    WHERE conversation_id = ?
                """, (conversation_id,))
                
                row = cursor.fetchone()
                if row:
                    return ConversationSummary(
                        conversation_id=row[0],
                        summary_text=row[1],
                        message_count=row[2],
                        created_at=datetime.fromisoformat(row[3]),
                        last_updated=datetime.fromisoformat(row[4])
                    )
                
                return None
                
        except Exception as e:
            log_error(e, "getting_conversation_summary", conversation_id=conversation_id)
            return None
    
    def create_conversation_summary(self, conversation_id: str, summary_text: str, 
                                  message_count: int) -> None:
        """Create or update conversation summary"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO conversation_summaries 
                    (conversation_id, summary_text, message_count, last_updated)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, (conversation_id, summary_text, message_count))
                
                conn.commit()
            
            log_operation("conversation_summary_created", 
                         conversation_id=conversation_id, 
                         message_count=message_count)
                
        except Exception as e:
            log_error(e, "creating_conversation_summary", conversation_id=conversation_id)
            raise
    
    def should_summarize_conversation(self, conversation_id: str, 
                                    summary_threshold: int = 10) -> bool:
        """Check if conversation should be summarized"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Count messages since last summary
                cursor.execute("""
                    SELECT COUNT(*) FROM messages 
                    WHERE conversation_id = ? 
                    AND timestamp > (
                        SELECT COALESCE(last_updated, '1970-01-01') 
                        FROM conversation_summaries 
                        WHERE conversation_id = ?
                    )
                """, (conversation_id, conversation_id))
                
                message_count = cursor.fetchone()[0]
                return message_count >= summary_threshold
                
        except Exception as e:
            log_error(e, "checking_summarization_threshold", conversation_id=conversation_id)
            return False
    
    def build_conversation_context(self, conversation_id: str, 
                                 max_history_tokens: int = 2000,
                                 include_summary: bool = True) -> str:
        """Build complete conversation context for LLM"""
        try:
            context_parts = []
            
            # Include conversation summary if available and requested
            if include_summary:
                summary = self.get_conversation_summary(conversation_id)
                if summary:
                    context_parts.append(f"Previous conversation summary: {summary.summary_text}")
            
            # Load recent history
            history = self.load_conversation_history(conversation_id, limit=10)
            if history:
                history_text = self.format_conversation_history(history, max_history_tokens)
                if history_text:
                    context_parts.append(f"Recent conversation history:\n{history_text}")
            
            return "\n\n".join(context_parts)
            
        except Exception as e:
            log_error(e, "building_conversation_context", conversation_id=conversation_id)
            return ""
    
    def list_conversations(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List recent conversations"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT c.conversation_id, c.title, c.created_at, c.last_updated,
                           COUNT(m.message_id) as message_count
                    FROM conversations c
                    LEFT JOIN messages m ON c.conversation_id = m.conversation_id
                    GROUP BY c.conversation_id
                    ORDER BY c.last_updated DESC
                    LIMIT ?
                """, (limit,))
                
                conversations = []
                for row in cursor.fetchall():
                    conversations.append({
                        "conversation_id": row[0],
                        "title": row[1],
                        "created_at": row[2],
                        "last_updated": row[3],
                        "message_count": row[4]
                    })
                
                return conversations
                
        except Exception as e:
            log_error(e, "listing_conversations")
            return []
    
    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation and all its messages"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Delete messages
                cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
                
                # Delete summary
                cursor.execute("DELETE FROM conversation_summaries WHERE conversation_id = ?", (conversation_id,))
                
                # Delete conversation
                cursor.execute("DELETE FROM conversations WHERE conversation_id = ?", (conversation_id,))
                
                conn.commit()
            
            log_operation("conversation_deleted", conversation_id=conversation_id)
            return True
            
        except Exception as e:
            log_error(e, "deleting_conversation", conversation_id=conversation_id)
            return False
    
    def cleanup_old_conversations(self, days_old: int = 30) -> int:
        """Clean up conversations older than specified days"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get conversations to delete
                cursor.execute("""
                    SELECT conversation_id FROM conversations 
                    WHERE last_updated < ?
                """, (cutoff_date.isoformat(),))
                
                conversation_ids = [row[0] for row in cursor.fetchall()]
                
                # Delete each conversation
                deleted_count = 0
                for conv_id in conversation_ids:
                    if self.delete_conversation(conv_id):
                        deleted_count += 1
                
                log_operation("conversations_cleaned_up", 
                             deleted_count=deleted_count, 
                             days_old=days_old)
                return deleted_count
                
        except Exception as e:
            log_error(e, "cleaning_up_old_conversations")
            return 0

# Global conversation manager instance
conversation_manager = ConversationManager()

# Export
__all__ = ['ConversationManager', 'ConversationMessage', 'ConversationSummary', 'conversation_manager']
