"""
Comprehensive System Test for Enhanced RAG System
Tests all components and integrations
"""
import asyncio
import time
import json
from datetime import datetime
from typing import Dict, Any

def test_configuration():
    """Test configuration system"""
    print("🔧 Testing Configuration System...")
    
    try:
        from config import config, config_manager
        
        # Test config loading
        assert config is not None, "Config not loaded"
        assert hasattr(config, 'rag_namespace'), "Missing rag_namespace"
        assert hasattr(config, 'pinecone'), "Missing pinecone config"
        assert hasattr(config, 'llm'), "Missing LLM config"
        
        print("✅ Configuration system working")
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

def test_logging():
    """Test logging system"""
    print("📝 Testing Logging System...")
    
    try:
        from logger import logger, log_operation, log_performance, log_error
        
        # Test basic logging
        logger.info("Test log message")
        log_operation("test_operation", test_param="test_value")
        log_performance("test_performance", 0.1, test_metric="test")
        log_error(Exception("Test error"), "test_error")
        
        print("✅ Logging system working")
        return True
        
    except Exception as e:
        print(f"❌ Logging test failed: {e}")
        return False

def test_file_system():
    """Test file system utilities"""
    print("📁 Testing File System Utilities...")
    
    try:
        from filesys import iter_files, load_one_local, doc_uid_for_path, doc_uid_for_content
        
        # Test file iteration
        test_files = iter_files(["docs"])
        assert isinstance(test_files, list), "iter_files should return list"
        
        # Test document UID generation
        test_path = "test_file.txt"
        uid1 = doc_uid_for_path(test_path)
        uid2 = doc_uid_for_path(test_path)
        assert uid1 == uid2, "Document UIDs should be consistent"
        
        print("✅ File system utilities working")
        return True
        
    except Exception as e:
        print(f"❌ File system test failed: {e}")
        return False

def test_conversation_manager():
    """Test conversation management"""
    print("💬 Testing Conversation Manager...")
    
    try:
        from conversation_manager import conversation_manager
        
        # Test conversation creation
        conv_id = conversation_manager.create_conversation(
            title="Test Conversation",
            metadata={"test": True}
        )
        assert conv_id is not None, "Conversation ID should not be None"
        
        # Test message saving
        msg_id = conversation_manager.save_message(
            conv_id, "user", "Test message"
        )
        assert msg_id is not None, "Message ID should not be None"
        
        # Test history loading
        history = conversation_manager.load_conversation_history(conv_id)
        assert len(history) == 1, "Should have 1 message in history"
        assert history[0].content == "Test message", "Message content should match"
        
        # Test context building
        context = conversation_manager.build_conversation_context(conv_id)
        assert isinstance(context, str), "Context should be a string"
        
        # Cleanup
        conversation_manager.delete_conversation(conv_id)
        
        print("✅ Conversation manager working")
        return True
        
    except Exception as e:
        print(f"❌ Conversation manager test failed: {e}")
        return False

def test_system_monitor():
    """Test system monitoring"""
    print("📊 Testing System Monitor...")
    
    try:
        from system_monitor import system_monitor
        
        # Test metrics collection
        system_status = system_monitor.get_system_status()
        assert isinstance(system_status, dict), "System status should be dict"
        assert "overall_status" in system_status, "Should have overall_status"
        
        # Test request recording
        system_monitor.record_request(0.1, False)
        system_monitor.record_request(0.2, True)
        
        # Test performance summary
        perf_summary = system_monitor.get_performance_summary()
        assert isinstance(perf_summary, dict), "Performance summary should be dict"
        
        print("✅ System monitor working")
        return True
        
    except Exception as e:
        print(f"❌ System monitor test failed: {e}")
        return False

def test_query_engine():
    """Test query engine (without external dependencies)"""
    print("🔍 Testing Query Engine...")
    
    try:
        from query_engine import QueryAnalyzer, QueryType
        
        # Test query analyzer
        analyzer = QueryAnalyzer()
        query_type, metadata = analyzer.analyze_query("What is machine learning?")
        
        assert isinstance(query_type, QueryType), "Query type should be QueryType enum"
        assert isinstance(metadata, dict), "Metadata should be dict"
        assert "length" in metadata, "Metadata should have length"
        
        print("✅ Query engine components working")
        return True
        
    except Exception as e:
        print(f"❌ Query engine test failed: {e}")
        return False

def test_api_models():
    """Test API models and validation"""
    print("🌐 Testing API Models...")
    
    try:
        from api_v2 import QueryRequest, IngestRequest, ConversationRequest
        
        # Test query request validation
        query_req = QueryRequest(question="Test question")
        assert query_req.question == "Test question", "Question should match"
        
        # Test validation
        try:
            QueryRequest(question="")  # Should fail
            assert False, "Empty question should fail validation"
        except ValueError:
            pass  # Expected
        
        # Test conversation request
        conv_req = ConversationRequest(title="Test")
        assert conv_req.title == "Test", "Title should match"
        
        print("✅ API models working")
        return True
        
    except Exception as e:
        print(f"❌ API models test failed: {e}")
        return False

def test_integration():
    """Test system integration"""
    print("🔗 Testing System Integration...")
    
    try:
        # Test conversation-aware flow
        from conversation_manager import conversation_manager
        from query_engine import QueryAnalyzer
        
        # Create conversation
        conv_id = conversation_manager.create_conversation(title="Integration Test")
        
        # Add messages
        conversation_manager.save_message(conv_id, "user", "Hello")
        conversation_manager.save_message(conv_id, "assistant", "Hi there!")
        
        # Test context building
        context = conversation_manager.build_conversation_context(conv_id)
        assert "Hello" in context, "Context should contain user message"
        assert "Hi there!" in context, "Context should contain assistant message"
        
        # Test query analysis
        analyzer = QueryAnalyzer()
        query_type, metadata = analyzer.analyze_query("How are you?")
        assert query_type == QueryType.FACTUAL, "Should be factual query"
        
        # Cleanup
        conversation_manager.delete_conversation(conv_id)
        
        print("✅ System integration working")
        return True
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False

def run_performance_test():
    """Run basic performance tests"""
    print("⚡ Running Performance Tests...")
    
    try:
        from conversation_manager import conversation_manager
        from query_engine import QueryAnalyzer
        
        # Test conversation creation performance
        start_time = time.time()
        conv_ids = []
        for i in range(10):
            conv_id = conversation_manager.create_conversation(title=f"Perf Test {i}")
            conv_ids.append(conv_id)
        creation_time = time.time() - start_time
        
        # Test query analysis performance
        analyzer = QueryAnalyzer()
        start_time = time.time()
        for i in range(100):
            analyzer.analyze_query(f"Test question {i}")
        analysis_time = time.time() - start_time
        
        # Test context building performance
        start_time = time.time()
        for conv_id in conv_ids:
            conversation_manager.build_conversation_context(conv_id)
        context_time = time.time() - start_time
        
        # Cleanup
        for conv_id in conv_ids:
            conversation_manager.delete_conversation(conv_id)
        
        print(f"✅ Performance test completed:")
        print(f"   - 10 conversations created in {creation_time:.3f}s")
        print(f"   - 100 queries analyzed in {analysis_time:.3f}s")
        print(f"   - 10 contexts built in {context_time:.3f}s")
        
        return True
        
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        return False

def main():
    """Run all system tests"""
    print("🧪 Enhanced RAG System - Comprehensive Test Suite")
    print("=" * 60)
    
    tests = [
        ("Configuration", test_configuration),
        ("Logging", test_logging),
        ("File System", test_file_system),
        ("Conversation Manager", test_conversation_manager),
        ("System Monitor", test_system_monitor),
        ("Query Engine", test_query_engine),
        ("API Models", test_api_models),
        ("System Integration", test_integration),
        ("Performance", run_performance_test)
    ]
    
    results = []
    start_time = time.time()
    
    for test_name, test_func in tests:
        print(f"\n🧪 Running: {test_name}")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {str(e)}")
            results.append((test_name, False))
    
    total_time = time.time() - start_time
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status} {test_name}")
    
    print(f"\n🎯 Results: {passed}/{total} tests passed")
    print(f"⏱️  Total time: {total_time:.2f} seconds")
    
    if passed == total:
        print("🎉 All tests passed! Enhanced RAG system is working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
