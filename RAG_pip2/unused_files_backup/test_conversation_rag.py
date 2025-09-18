"""
Test script for conversation-aware RAG system
Demonstrates the new conversation flow with memory management
"""
import asyncio
import json
from datetime import datetime

from query_engine import EnhancedQueryEngine
from conversation_manager import conversation_manager
from config import config

def test_conversation_flow():
    """Test the complete conversation-aware RAG flow"""
    print("🚀 Testing Conversation-Aware RAG System")
    print("=" * 50)
    
    try:
        # Initialize query engine
        print("📝 Initializing query engine...")
        engine = EnhancedQueryEngine(config.rag_namespace)
        print("✅ Query engine initialized")
        
        # Test 1: Create a new conversation
        print("\n🔗 Test 1: Creating new conversation")
        conversation_id = conversation_manager.create_conversation(
            title="RAG System Testing",
            metadata={"test": True, "created_at": datetime.now().isoformat()}
        )
        print(f"✅ Created conversation: {conversation_id}")
        
        # Test 2: First question (no history)
        print("\n❓ Test 2: First question (no conversation history)")
        question1 = "What is machine learning?"
        print(f"Question: {question1}")
        
        result1 = engine.answer_question(question1, conversation_id)
        print(f"Answer: {result1.answer[:200]}...")
        print(f"Confidence: {result1.confidence:.2f}")
        print(f"Sources: {len(result1.sources)}")
        
        # Test 3: Follow-up question (with history)
        print("\n❓ Test 3: Follow-up question (with conversation history)")
        question2 = "Can you give me a specific example?"
        print(f"Question: {question2}")
        
        result2 = engine.answer_question(question2, conversation_id)
        print(f"Answer: {result2.answer[:200]}...")
        print(f"Confidence: {result2.confidence:.2f}")
        print(f"Sources: {len(result2.sources)}")
        
        # Test 4: Another follow-up
        print("\n❓ Test 4: Another follow-up question")
        question3 = "What are the main types of machine learning?"
        print(f"Question: {question3}")
        
        result3 = engine.answer_question(question3, conversation_id)
        print(f"Answer: {result3.answer[:200]}...")
        print(f"Confidence: {result3.confidence:.2f}")
        print(f"Sources: {len(result3.sources)}")
        
        # Test 5: Load conversation history
        print("\n📚 Test 5: Loading conversation history")
        history = conversation_manager.load_conversation_history(conversation_id, limit=10)
        print(f"✅ Loaded {len(history)} messages from conversation")
        
        for i, msg in enumerate(history, 1):
            role_emoji = "👤" if msg.role == "user" else "🤖"
            print(f"  {i}. {role_emoji} {msg.role}: {msg.content[:100]}...")
        
        # Test 6: Test conversation context building
        print("\n🧠 Test 6: Testing conversation context building")
        context = conversation_manager.build_conversation_context(
            conversation_id, max_history_tokens=1000, include_summary=False
        )
        print(f"✅ Built context ({len(context)} characters)")
        print(f"Context preview: {context[:200]}...")
        
        # Test 7: Test without conversation_id (should work like before)
        print("\n🔄 Test 7: Testing without conversation_id (backward compatibility)")
        question4 = "What is artificial intelligence?"
        print(f"Question: {question4}")
        
        result4 = engine.query(question4)  # No conversation_id
        print(f"Answer: {result4.answer[:200]}...")
        print(f"Confidence: {result4.confidence:.2f}")
        print(f"Sources: {len(result4.sources)}")
        
        # Test 8: List conversations
        print("\n📋 Test 8: Listing conversations")
        conversations = conversation_manager.list_conversations(limit=10)
        print(f"✅ Found {len(conversations)} conversations")
        
        for conv in conversations:
            print(f"  - {conv['conversation_id'][:8]}... | {conv['title']} | {conv['message_count']} messages")
        
        print("\n🎉 All tests completed successfully!")
        print(f"📊 Final conversation has {len(history)} messages")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_conversation_summarization():
    """Test conversation summarization feature"""
    print("\n🧠 Testing Conversation Summarization")
    print("=" * 40)
    
    try:
        # Create a conversation with many messages
        conversation_id = conversation_manager.create_conversation(
            title="Summarization Test",
            metadata={"test": "summarization"}
        )
        
        # Add multiple messages to trigger summarization
        test_questions = [
            "What is machine learning?",
            "How does supervised learning work?",
            "What are neural networks?",
            "Explain deep learning",
            "What is reinforcement learning?",
            "How do you train a model?",
            "What is overfitting?",
            "Explain cross-validation",
            "What are hyperparameters?",
            "How do you evaluate model performance?",
            "What is the bias-variance tradeoff?",
            "Explain ensemble methods"
        ]
        
        engine = EnhancedQueryEngine(config.rag_namespace)
        
        print(f"📝 Adding {len(test_questions)} messages to conversation...")
        for i, question in enumerate(test_questions, 1):
            print(f"  {i}. {question}")
            result = engine.answer_question(question, conversation_id)
            print(f"     ✅ Answered (confidence: {result.confidence:.2f})")
        
        # Check if summarization should be triggered
        should_summarize = conversation_manager.should_summarize_conversation(
            conversation_id, summary_threshold=10
        )
        print(f"\n🔍 Should summarize: {should_summarize}")
        
        if should_summarize:
            print("📝 Creating conversation summary...")
            engine._create_conversation_summary(conversation_id)
            
            # Get the summary
            summary = conversation_manager.get_conversation_summary(conversation_id)
            if summary:
                print(f"✅ Summary created:")
                print(f"   Message count: {summary.message_count}")
                print(f"   Summary: {summary.summary_text[:300]}...")
            else:
                print("❌ No summary found")
        
        return True
        
    except Exception as e:
        print(f"❌ Summarization test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_api_compatibility():
    """Test API compatibility with conversation features"""
    print("\n🔌 Testing API Compatibility")
    print("=" * 30)
    
    try:
        # Test the new answer_question method
        engine = EnhancedQueryEngine(config.rag_namespace)
        
        # Test with conversation_id
        conversation_id = conversation_manager.create_conversation(title="API Test")
        result = engine.answer_question("What is Python?", conversation_id)
        
        print(f"✅ API test with conversation_id: {result.metadata.get('conversation_id')}")
        
        # Test without conversation_id (should create new conversation)
        result2 = engine.answer_question("What is JavaScript?")
        print(f"✅ API test without conversation_id: {result2.metadata.get('conversation_id')}")
        
        return True
        
    except Exception as e:
        print(f"❌ API compatibility test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧪 Conversation-Aware RAG System Test Suite")
    print("=" * 50)
    
    # Run all tests
    tests = [
        ("Basic Conversation Flow", test_conversation_flow),
        ("Conversation Summarization", test_conversation_summarization),
        ("API Compatibility", test_api_compatibility)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n🧪 Running: {test_name}")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {str(e)}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status} {test_name}")
    
    print(f"\n🎯 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Conversation-aware RAG system is working correctly.")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
