"""
🚀 Enhanced RAG System - Beautiful Startup Script
Elegant system initialization with beautiful output and health checks
"""
import os
import sys
import time
import asyncio
from datetime import datetime
from pathlib import Path

# Beautiful console output
class Colors:
    """ANSI color codes for beautiful output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_banner():
    """Print beautiful system banner"""
    banner = f"""
{Colors.HEADER}{Colors.BOLD}
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║    🚀 ENHANCED RAG SYSTEM - CONVERSATION-AWARE AI          ║
║                                                              ║
║    ✨ Features:                                              ║
║    • Conversation Memory Management                          ║
║    • Real-time System Monitoring                            ║
║    • Advanced Query Processing                              ║
║    • Production-Ready APIs                                  ║
║    • Beautiful Dashboard Interface                          ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
{Colors.ENDC}
"""
    print(banner)

def print_step(step_num: int, total_steps: int, message: str, status: str = "info"):
    """Print a beautiful step with progress"""
    colors = {
        "info": Colors.OKBLUE,
        "success": Colors.OKGREEN,
        "warning": Colors.WARNING,
        "error": Colors.FAIL
    }
    
    color = colors.get(status, Colors.OKBLUE)
    progress = f"[{step_num}/{total_steps}]"
    
    print(f"{color}{Colors.BOLD}{progress}{Colors.ENDC} {message}")

def check_environment():
    """Check environment setup"""
    print_step(1, 6, "🔍 Checking environment setup...", "info")
    
    issues = []
    
    # Check Python version
    if sys.version_info < (3, 8):
        issues.append("Python 3.8+ required")
    
    # Check required files
    required_files = [
        "RAG_pip2/config.py",
        "RAG_pip2/query_engine.py", 
        "RAG_pip2/conversation_manager.py",
        "RAG_pip2/api_v2.py",
        "RAG_pip2/dashboard_server.py"
    ]
    
    for file in required_files:
        if not Path(file).exists():
            issues.append(f"Missing file: {file}")
    
    # Check .env file
    if not Path("RAG_pip2/.env").exists():
        issues.append("Missing .env file")
    
    if issues:
        print_step(1, 6, f"❌ Environment issues found: {', '.join(issues)}", "error")
        return False
    else:
        print_step(1, 6, "✅ Environment setup complete", "success")
        return True

def check_dependencies():
    """Check required dependencies"""
    print_step(2, 6, "📦 Checking dependencies...", "info")
    
    required_packages = [
        "fastapi",
        "uvicorn", 
        "langchain",
        "pinecone",
        "pydantic"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print_step(2, 6, f"⚠️  Missing packages: {', '.join(missing_packages)}", "warning")
        print(f"{Colors.WARNING}   Install with: pip install {' '.join(missing_packages)}{Colors.ENDC}")
        return False
    else:
        print_step(2, 6, "✅ All dependencies available", "success")
        return True

def check_configuration():
    """Check system configuration"""
    print_step(3, 6, "⚙️  Checking configuration...", "info")
    
    try:
        from config import config
        
        # Check required config
        required_config = [
            ("PINECONE_API_KEY", config.pinecone_api_key),
            ("GOOGLE_API_KEY", config.google_api_key),
            ("PINECONE_INDEX_NAME", config.pinecone.index_name),
            ("RAG_NAMESPACE", config.rag_namespace)
        ]
        
        missing_config = []
        for name, value in required_config:
            if not value:
                missing_config.append(name)
        
        if missing_config:
            print_step(3, 6, f"⚠️  Missing config: {', '.join(missing_config)}", "warning")
            return False
        else:
            print_step(3, 6, "✅ Configuration complete", "success")
            return True
            
    except Exception as e:
        print_step(3, 6, f"❌ Configuration error: {str(e)}", "error")
        return False

def test_components():
    """Test system components"""
    print_step(4, 6, "🧪 Testing system components...", "info")
    
    try:
        # Test conversation manager
        from conversation_manager import conversation_manager
        conv_id = conversation_manager.create_conversation(title="Test")
        conversation_manager.delete_conversation(conv_id)
        
        # Test query analyzer
        from query_engine import QueryAnalyzer
        analyzer = QueryAnalyzer()
        analyzer.analyze_query("Test query")
        
        print_step(4, 6, "✅ System components working", "success")
        return True
        
    except Exception as e:
        print_step(4, 6, f"❌ Component test failed: {str(e)}", "error")
        return False

def start_services():
    """Start system services"""
    print_step(5, 6, "🚀 Starting system services...", "info")
    
    try:
        # Import and initialize services
        from conversation_manager import conversation_manager
        from query_engine import EnhancedQueryEngine
        
        # Initialize query engine
        query_engine = EnhancedQueryEngine()
        
        print_step(5, 6, "✅ System services started", "success")
        return True
        
    except Exception as e:
        print_step(5, 6, f"❌ Service startup failed: {str(e)}", "error")
        return False

def show_system_info():
    """Show system information and next steps"""
    print_step(6, 6, "📊 System ready! Here's what you can do:", "success")
    
    print(f"""
{Colors.OKGREEN}{Colors.BOLD}🎉 Your Enhanced RAG System is Ready!{Colors.ENDC}

{Colors.OKCYAN}📡 Available Services:{Colors.ENDC}
   • API Server: python start_api.py
   • Dashboard: python dashboard_server.py
   • CLI Tools: python cli.py --help

{Colors.OKCYAN}🌐 Endpoints:{Colors.ENDC}
   • API Docs: http://localhost:8000/docs
   • Dashboard: http://localhost:8000
   • Health Check: http://localhost:8000/health

{Colors.OKCYAN}💬 Conversation Features:{Colors.ENDC}
   • Create conversations with memory
   • Context-aware responses
   • Automatic summarization
   • Conversation history management

{Colors.OKCYAN}📊 Monitoring:{Colors.ENDC}
   • Real-time system metrics
   • Performance monitoring
   • Health checks
   • Error tracking

{Colors.WARNING}💡 Pro Tips:{Colors.ENDC}
   • Use conversation_id for context-aware queries
   • Check /health endpoint for system status
   • Monitor /metrics for performance data
   • Use the dashboard for easy interaction

{Colors.HEADER}🚀 Happy querying with your enhanced RAG system!{Colors.ENDC}
""")

def main():
    """Main startup function"""
    print_banner()
    
    print(f"{Colors.OKBLUE}🕐 Starting system initialization at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.ENDC}\n")
    
    # Run all checks
    checks = [
        check_environment,
        check_dependencies, 
        check_configuration,
        test_components,
        start_services
    ]
    
    all_passed = True
    for check in checks:
        if not check():
            all_passed = False
            break
        time.sleep(0.5)  # Small delay for better UX
    
    print(f"\n{Colors.OKBLUE}{'='*60}{Colors.ENDC}")
    
    if all_passed:
        show_system_info()
        return True
    else:
        print(f"{Colors.FAIL}{Colors.BOLD}❌ System initialization failed!{Colors.ENDC}")
        print(f"{Colors.WARNING}Please fix the issues above and try again.{Colors.ENDC}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
