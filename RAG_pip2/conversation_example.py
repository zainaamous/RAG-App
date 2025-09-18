"""
Example usage of conversation-aware RAG system
Demonstrates the new flow: User Query → Fetch conversation history → Build context → LLM Answer
"""
from query_engine import EnhancedQueryEngine
from conversation_manager import conversation_manager
from config import config

def main():
    """Example conversation flow"""
    print("🤖 Conversation-Aware RAG Example")
    print("=" * 40)
    
    # Initialize the enhanced query engine
    engine = EnhancedQueryEngine(config.rag_namespace)
    
    # Create a new conversation
    conversation_id = conversation_manager.create_conversation(
        title="Machine Learning Discussion",
        metadata={"topic": "ML", "user": "example_user"}
    )
    
    print(f"📝 Created conversation: {conversation_id}")
    print()
    
    # Example conversation flow
    questions = [
        "What is machine learning?",
        "Can you give me a specific example of supervised learning?",
        "How does that relate to neural networks?",
        "What are the advantages of deep learning?",
        "Can you summarize what we've discussed so far?"
    ]
    
    for i, question in enumerate(questions, 1):
        print(f"👤 User: {question}")
        
        # This is the new conversation-aware flow:
        # 1. Load conversation history
        # 2. Build context (history + docs)
        # 3. Generate answer with full context
        # 4. Save the conversation turn
        result = engine.answer_question(question, conversation_id)
        
        print(f"🤖 Assistant: {result.answer}")
        print(f"📊 Confidence: {result.confidence:.2f} | Sources: {len(result.sources)}")
        print()
    
    # Show conversation history
    print("📚 Conversation History:")
    history = conversation_manager.load_conversation_history(conversation_id)
    
    for msg in history:
        role_emoji = "👤" if msg.role == "user" else "🤖"
        print(f"  {role_emoji} {msg.role}: {msg.content}")
    
    print(f"\n✅ Conversation completed with {len(history)} messages")

if __name__ == "__main__":
    main()
