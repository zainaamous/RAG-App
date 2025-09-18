"""
🚀 Enhanced RAG System - Beautiful Launcher
One-click system launcher with beautiful interface and service management
"""
import os
import sys
import time
import subprocess
import threading
import signal
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

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

class ServiceManager:
    """Beautiful service manager for RAG system"""
    
    def __init__(self):
        self.services = {}
        self.running = False
    
    def print_banner(self):
        """Print beautiful launcher banner"""
        banner = f"""
{Colors.HEADER}{Colors.BOLD}
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║    🚀 ENHANCED RAG SYSTEM - BEAUTIFUL LAUNCHER              ║
║                                                              ║
║    ✨ One-Click System Management                            ║
║    🎯 Production-Ready Deployment                            ║
║    📊 Real-time Monitoring                                   ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
{Colors.ENDC}
"""
        print(banner)
    
    def print_menu(self):
        """Print beautiful menu"""
        menu = f"""
{Colors.OKCYAN}{Colors.BOLD}🎯 SYSTEM LAUNCHER MENU{Colors.ENDC}
{Colors.OKBLUE}{'─' * 50}{Colors.ENDC}

{Colors.OKGREEN}1.{Colors.ENDC} 🚀 Start All Services (API + Dashboard)
{Colors.OKGREEN}2.{Colors.ENDC} 📡 Start API Server Only
{Colors.OKGREEN}3.{Colors.ENDC} 🎨 Start Dashboard Only
{Colors.OKGREEN}4.{Colors.ENDC} 📊 System Status Check
{Colors.OKGREEN}5.{Colors.ENDC} 🧪 Run System Tests
{Colors.OKGREEN}6.{Colors.ENDC} 📋 Show System Info
{Colors.OKGREEN}7.{Colors.ENDC} 🔧 Configuration Check
{Colors.OKGREEN}8.{Colors.ENDC} 📚 Show Documentation
{Colors.OKGREEN}9.{Colors.ENDC} 🛑 Stop All Services
{Colors.OKGREEN}0.{Colors.ENDC} 🚪 Exit

{Colors.OKBLUE}{'─' * 50}{Colors.ENDC}
"""
        print(menu)
    
    def start_api_server(self) -> bool:
        """Start API server"""
        print(f"{Colors.OKBLUE}🚀 Starting API Server...{Colors.ENDC}")
        
        try:
            # Check if already running
            if "api" in self.services and self.services["api"].poll() is None:
                print(f"{Colors.WARNING}⚠️  API server already running{Colors.ENDC}")
                return True
            
            # Start API server
            process = subprocess.Popen([
                sys.executable, "start_api.py"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            self.services["api"] = process
            
            # Wait a moment and check if it started
            time.sleep(2)
            if process.poll() is None:
                print(f"{Colors.OKGREEN}✅ API Server started successfully{Colors.ENDC}")
                print(f"{Colors.OKCYAN}   📡 API Docs: http://localhost:8000/docs{Colors.ENDC}")
                print(f"{Colors.OKCYAN}   🏥 Health: http://localhost:8000/health{Colors.ENDC}")
                return True
            else:
                print(f"{Colors.FAIL}❌ API Server failed to start{Colors.ENDC}")
                return False
                
        except Exception as e:
            print(f"{Colors.FAIL}❌ Error starting API server: {e}{Colors.ENDC}")
            return False
    
    def start_dashboard(self) -> bool:
        """Start dashboard server"""
        print(f"{Colors.OKBLUE}🎨 Starting Dashboard...{Colors.ENDC}")
        
        try:
            # Check if already running
            if "dashboard" in self.services and self.services["dashboard"].poll() is None:
                print(f"{Colors.WARNING}⚠️  Dashboard already running{Colors.ENDC}")
                return True
            
            # Start dashboard
            process = subprocess.Popen([
                sys.executable, "dashboard_server.py"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            self.services["dashboard"] = process
            
            # Wait a moment and check if it started
            time.sleep(2)
            if process.poll() is None:
                print(f"{Colors.OKGREEN}✅ Dashboard started successfully{Colors.ENDC}")
                print(f"{Colors.OKCYAN}   🎨 Dashboard: http://localhost:8080{Colors.ENDC}")
                return True
            else:
                print(f"{Colors.FAIL}❌ Dashboard failed to start{Colors.ENDC}")
                return False
                
        except Exception as e:
            print(f"{Colors.FAIL}❌ Error starting dashboard: {e}{Colors.ENDC}")
            return False
    
    def start_all_services(self) -> bool:
        """Start all services"""
        print(f"{Colors.OKBLUE}🚀 Starting all services...{Colors.ENDC}")
        
        success = True
        
        # Start API server
        if not self.start_api_server():
            success = False
        
        time.sleep(1)
        
        # Start dashboard
        if not self.start_dashboard():
            success = False
        
        if success:
            print(f"\n{Colors.OKGREEN}{Colors.BOLD}🎉 All services started successfully!{Colors.ENDC}")
            self.show_service_urls()
        else:
            print(f"\n{Colors.FAIL}{Colors.BOLD}❌ Some services failed to start{Colors.ENDC}")
        
        return success
    
    def stop_all_services(self):
        """Stop all services"""
        print(f"{Colors.WARNING}🛑 Stopping all services...{Colors.ENDC}")
        
        for name, process in self.services.items():
            if process.poll() is None:  # Still running
                print(f"{Colors.OKBLUE}   Stopping {name}...{Colors.ENDC}")
                process.terminate()
                try:
                    process.wait(timeout=5)
                    print(f"{Colors.OKGREEN}   ✅ {name} stopped{Colors.ENDC}")
                except subprocess.TimeoutExpired:
                    print(f"{Colors.WARNING}   ⚠️  Force killing {name}...{Colors.ENDC}")
                    process.kill()
                    process.wait()
                    print(f"{Colors.OKGREEN}   ✅ {name} force stopped{Colors.ENDC}")
        
        self.services.clear()
        print(f"{Colors.OKGREEN}✅ All services stopped{Colors.ENDC}")
    
    def show_service_urls(self):
        """Show service URLs"""
        print(f"\n{Colors.OKCYAN}{Colors.BOLD}🔗 SERVICE URLs{Colors.ENDC}")
        print(f"{Colors.OKBLUE}{'─' * 50}{Colors.ENDC}")
        print(f"📡 API Server: {Colors.OKGREEN}http://localhost:8000{Colors.ENDC}")
        print(f"📚 API Docs: {Colors.OKGREEN}http://localhost:8000/docs{Colors.ENDC}")
        print(f"🏥 Health Check: {Colors.OKGREEN}http://localhost:8000/health{Colors.ENDC}")
        print(f"📊 Metrics: {Colors.OKGREEN}http://localhost:8000/metrics{Colors.ENDC}")
        print(f"🎨 Dashboard: {Colors.OKGREEN}http://localhost:8080{Colors.ENDC}")
    
    def check_system_status(self):
        """Check system status"""
        print(f"{Colors.OKBLUE}📊 Checking system status...{Colors.ENDC}")
        
        try:
            # Run system status checker
            result = subprocess.run([
                sys.executable, "system_status.py"
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                print(result.stdout)
            else:
                print(f"{Colors.WARNING}⚠️  Status check failed: {result.stderr}{Colors.ENDC}")
                
        except Exception as e:
            print(f"{Colors.FAIL}❌ Error checking status: {e}{Colors.ENDC}")
    
    def run_system_tests(self):
        """Run system tests"""
        print(f"{Colors.OKBLUE}🧪 Running system tests...{Colors.ENDC}")
        
        try:
            # Run system test
            result = subprocess.run([
                sys.executable, "system_test.py"
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                print(result.stdout)
            else:
                print(f"{Colors.WARNING}⚠️  Some tests failed: {result.stderr}{Colors.ENDC}")
                
        except Exception as e:
            print(f"{Colors.FAIL}❌ Error running tests: {e}{Colors.ENDC}")
    
    def show_system_info(self):
        """Show system information"""
        print(f"\n{Colors.OKCYAN}{Colors.BOLD}📋 SYSTEM INFORMATION{Colors.ENDC}")
        print(f"{Colors.OKBLUE}{'─' * 50}{Colors.ENDC}")
        
        # Python version
        print(f"Python Version: {Colors.OKGREEN}{sys.version.split()[0]}{Colors.ENDC}")
        
        # Current directory
        print(f"Working Directory: {Colors.OKGREEN}{os.getcwd()}{Colors.ENDC}")
        
        # Available files
        important_files = [
            "config.py", "api_v2.py", "dashboard_server.py",
            "query_engine.py", "conversation_manager.py",
            "start_api.py", "system_test.py", "system_status.py"
        ]
        
        print(f"\n{Colors.OKCYAN}📁 Important Files:{Colors.ENDC}")
        for file in important_files:
            if Path(file).exists():
                print(f"  ✅ {file}")
            else:
                print(f"  ❌ {file}")
        
        # Service status
        print(f"\n{Colors.OKCYAN}🔧 Service Status:{Colors.ENDC}")
        for name, process in self.services.items():
            if process.poll() is None:
                print(f"  ✅ {name} - Running")
            else:
                print(f"  ❌ {name} - Stopped")
    
    def check_configuration(self):
        """Check configuration"""
        print(f"{Colors.OKBLUE}🔧 Checking configuration...{Colors.ENDC}")
        
        try:
            # Run configuration check
            result = subprocess.run([
                sys.executable, "start_system.py"
            ], capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0:
                print(result.stdout)
            else:
                print(f"{Colors.WARNING}⚠️  Configuration issues found{Colors.ENDC}")
                print(result.stderr)
                
        except Exception as e:
            print(f"{Colors.FAIL}❌ Error checking configuration: {e}{Colors.ENDC}")
    
    def show_documentation(self):
        """Show documentation"""
        print(f"\n{Colors.OKCYAN}{Colors.BOLD}📚 DOCUMENTATION{Colors.ENDC}")
        print(f"{Colors.OKBLUE}{'─' * 50}{Colors.ENDC}")
        
        docs = [
            ("API Documentation", "API_README.md"),
            ("System Architecture", "API_Architecture.md"),
            ("Enhanced Features", "ENHANCED_README.md"),
            ("Conversation RAG", "CONVERSATION_RAG_README.md"),
            ("Project Cleanup", "PROJECT_CLEANUP_ANALYSIS.md"),
            ("System Enhancement", "SYSTEM_ENHANCEMENT_SUMMARY.md")
        ]
        
        for title, filename in docs:
            if Path(filename).exists():
                print(f"📖 {title}: {Colors.OKGREEN}{filename}{Colors.ENDC}")
            else:
                print(f"❌ {title}: {Colors.FAIL}{filename}{Colors.ENDC}")
        
        print(f"\n{Colors.OKCYAN}🌐 Online Resources:{Colors.ENDC}")
        print(f"📡 API Docs: {Colors.OKGREEN}http://localhost:8000/docs{Colors.ENDC}")
        print(f"🎨 Dashboard: {Colors.OKGREEN}http://localhost:8080{Colors.ENDC}")
    
    def run(self):
        """Run the launcher"""
        self.print_banner()
        
        # Setup signal handler for graceful shutdown
        def signal_handler(signum, frame):
            print(f"\n{Colors.WARNING}🛑 Shutting down gracefully...{Colors.ENDC}")
            self.stop_all_services()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        while True:
            self.print_menu()
            
            try:
                choice = input(f"{Colors.OKCYAN}Enter your choice (0-9): {Colors.ENDC}").strip()
                
                if choice == "1":
                    self.start_all_services()
                elif choice == "2":
                    self.start_api_server()
                elif choice == "3":
                    self.start_dashboard()
                elif choice == "4":
                    self.check_system_status()
                elif choice == "5":
                    self.run_system_tests()
                elif choice == "6":
                    self.show_system_info()
                elif choice == "7":
                    self.check_configuration()
                elif choice == "8":
                    self.show_documentation()
                elif choice == "9":
                    self.stop_all_services()
                elif choice == "0":
                    print(f"{Colors.OKGREEN}👋 Goodbye!{Colors.ENDC}")
                    self.stop_all_services()
                    break
                else:
                    print(f"{Colors.WARNING}⚠️  Invalid choice. Please try again.{Colors.ENDC}")
                
                if choice != "0":
                    input(f"\n{Colors.OKBLUE}Press Enter to continue...{Colors.ENDC}")
                    print("\n" + "="*60 + "\n")
                
            except KeyboardInterrupt:
                print(f"\n{Colors.WARNING}🛑 Shutting down gracefully...{Colors.ENDC}")
                self.stop_all_services()
                break
            except Exception as e:
                print(f"{Colors.FAIL}❌ Error: {e}{Colors.ENDC}")

def main():
    """Main function"""
    launcher = ServiceManager()
    launcher.run()

if __name__ == "__main__":
    main()
