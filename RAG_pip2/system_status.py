"""
🎯 Enhanced RAG System - Beautiful Status Checker
Real-time system status with beautiful output and health monitoring
"""
import time
import requests
import json
from datetime import datetime
from typing import Dict, Any, Optional

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

class SystemStatusChecker:
    """Beautiful system status checker"""
    
    def __init__(self, api_url: str = "http://localhost:8000", dashboard_url: str = "http://localhost:8080"):
        self.api_url = api_url
        self.dashboard_url = dashboard_url
    
    def print_header(self):
        """Print beautiful header"""
        print(f"""
{Colors.HEADER}{Colors.BOLD}
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║    🎯 ENHANCED RAG SYSTEM - STATUS MONITOR                  ║
║                                                              ║
║    📊 Real-time System Health & Performance                 ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
{Colors.ENDC}
""")
    
    def check_api_health(self) -> Optional[Dict[str, Any]]:
        """Check API health"""
        try:
            response = requests.get(f"{self.api_url}/health", timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                return None
        except Exception:
            return None
    
    def check_dashboard_health(self) -> bool:
        """Check dashboard health"""
        try:
            response = requests.get(f"{self.dashboard_url}/", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def get_system_metrics(self) -> Optional[Dict[str, Any]]:
        """Get system metrics"""
        try:
            response = requests.get(f"{self.api_url}/metrics", timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                return None
        except Exception:
            return None
    
    def get_system_stats(self) -> Optional[Dict[str, Any]]:
        """Get system statistics"""
        try:
            response = requests.get(f"{self.api_url}/stats", timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                return None
        except Exception:
            return None
    
    def format_status(self, status: str) -> str:
        """Format status with colors"""
        if status == "healthy":
            return f"{Colors.OKGREEN}✅ HEALTHY{Colors.ENDC}"
        elif status == "degraded":
            return f"{Colors.WARNING}⚠️  DEGRADED{Colors.ENDC}"
        else:
            return f"{Colors.FAIL}❌ UNHEALTHY{Colors.ENDC}"
    
    def format_number(self, num: Any) -> str:
        """Format numbers nicely"""
        if isinstance(num, (int, float)):
            if num >= 1000000:
                return f"{num/1000000:.1f}M"
            elif num >= 1000:
                return f"{num/1000:.1f}K"
            else:
                return str(num)
        return str(num)
    
    def print_health_status(self, health_data: Dict[str, Any]):
        """Print health status beautifully"""
        print(f"{Colors.OKCYAN}{Colors.BOLD}🏥 SYSTEM HEALTH{Colors.ENDC}")
        print(f"{Colors.OKBLUE}{'─' * 50}{Colors.ENDC}")
        
        # Overall status
        overall_status = health_data.get("status", "unknown")
        print(f"Overall Status: {self.format_status(overall_status)}")
        
        # Uptime
        uptime = health_data.get("uptime", "N/A")
        print(f"Uptime: {Colors.OKGREEN}{uptime}{Colors.ENDC}")
        
        # Vector count
        vector_count = health_data.get("vector_count", 0)
        print(f"Vector Count: {Colors.OKGREEN}{self.format_number(vector_count)}{Colors.ENDC}")
        
        # System info
        system_info = health_data.get("system_info", {})
        if system_info:
            print(f"\n{Colors.OKCYAN}📊 SYSTEM INFO{Colors.ENDC}")
            print(f"{Colors.OKBLUE}{'─' * 50}{Colors.ENDC}")
            
            version = system_info.get("version", "N/A")
            print(f"Version: {Colors.OKGREEN}{version}{Colors.ENDC}")
            
            config = system_info.get("config", {})
            if config:
                print(f"Chunk Size: {Colors.OKGREEN}{config.get('chunk_size', 'N/A')}{Colors.ENDC}")
                print(f"Embedding Model: {Colors.OKGREEN}{config.get('embedding_model', 'N/A')}{Colors.ENDC}")
                print(f"LLM Model: {Colors.OKGREEN}{config.get('llm_model', 'N/A')}{Colors.ENDC}")
            
            # Component health
            component_health = system_info.get("component_health", {})
            if component_health:
                print(f"\n{Colors.OKCYAN}🔧 COMPONENT HEALTH{Colors.ENDC}")
                print(f"{Colors.OKBLUE}{'─' * 50}{Colors.ENDC}")
                
                for component, status in component_health.items():
                    print(f"{component.title()}: {self.format_status(status)}")
    
    def print_performance_metrics(self, metrics_data: Dict[str, Any]):
        """Print performance metrics beautifully"""
        print(f"\n{Colors.OKCYAN}{Colors.BOLD}⚡ PERFORMANCE METRICS{Colors.ENDC}")
        print(f"{Colors.OKBLUE}{'─' * 50}{Colors.ENDC}")
        
        performance = metrics_data.get("performance_summary", {})
        if performance and "message" not in performance:
            total_requests = performance.get("total_requests", 0)
            error_count = performance.get("total_errors", 0)
            error_rate = performance.get("error_rate_percent", 0)
            avg_response = performance.get("avg_response_time", 0)
            
            print(f"Total Requests: {Colors.OKGREEN}{self.format_number(total_requests)}{Colors.ENDC}")
            print(f"Error Count: {Colors.WARNING if error_count > 0 else Colors.OKGREEN}{self.format_number(error_count)}{Colors.ENDC}")
            print(f"Error Rate: {Colors.WARNING if error_rate > 5 else Colors.OKGREEN}{error_rate:.1f}%{Colors.ENDC}")
            print(f"Avg Response Time: {Colors.OKGREEN if avg_response < 1 else Colors.WARNING}{avg_response:.3f}s{Colors.ENDC}")
            
            if "p95_response_time" in performance:
                p95 = performance["p95_response_time"]
                p99 = performance["p99_response_time"]
                print(f"P95 Response Time: {Colors.OKGREEN if p95 < 2 else Colors.WARNING}{p95:.3f}s{Colors.ENDC}")
                print(f"P99 Response Time: {Colors.OKGREEN if p99 < 5 else Colors.WARNING}{p99:.3f}s{Colors.ENDC}")
        else:
            print(f"{Colors.WARNING}Performance data not available{Colors.ENDC}")
    
    def print_service_status(self):
        """Print service status"""
        print(f"\n{Colors.OKCYAN}{Colors.BOLD}🌐 SERVICE STATUS{Colors.ENDC}")
        print(f"{Colors.OKBLUE}{'─' * 50}{Colors.ENDC}")
        
        # API status
        api_health = self.check_api_health()
        api_status = "✅ ONLINE" if api_health else "❌ OFFLINE"
        api_color = Colors.OKGREEN if api_health else Colors.FAIL
        print(f"API Server: {api_color}{api_status}{Colors.ENDC}")
        
        # Dashboard status
        dashboard_health = self.check_dashboard_health()
        dashboard_status = "✅ ONLINE" if dashboard_health else "❌ OFFLINE"
        dashboard_color = Colors.OKGREEN if dashboard_health else Colors.FAIL
        print(f"Dashboard: {dashboard_color}{dashboard_status}{Colors.ENDC}")
        
        # URLs
        print(f"\n{Colors.OKCYAN}🔗 URLs{Colors.ENDC}")
        print(f"API Docs: {Colors.OKBLUE}{self.api_url}/docs{Colors.ENDC}")
        print(f"Dashboard: {Colors.OKBLUE}{self.dashboard_url}{Colors.ENDC}")
        print(f"Health Check: {Colors.OKBLUE}{self.api_url}/health{Colors.ENDC}")
    
    def print_recent_activity(self, metrics_data: Dict[str, Any]):
        """Print recent activity"""
        print(f"\n{Colors.OKCYAN}{Colors.BOLD}📈 RECENT ACTIVITY{Colors.ENDC}")
        print(f"{Colors.OKBLUE}{'─' * 50}{Colors.ENDC}")
        
        metrics_history = metrics_data.get("metrics_history", [])
        if metrics_history:
            recent = metrics_history[-5:]  # Last 5 entries
            for metric in recent:
                timestamp = metric.get("timestamp", "N/A")
                cpu = metric.get("cpu_percent", 0)
                memory = metric.get("memory_percent", 0)
                requests = metric.get("request_count", 0)
                
                print(f"{timestamp}: CPU {cpu:.1f}% | Memory {memory:.1f}% | Requests {requests}")
        else:
            print(f"{Colors.WARNING}No recent activity data available{Colors.ENDC}")
    
    def run_status_check(self):
        """Run complete status check"""
        self.print_header()
        
        print(f"{Colors.OKBLUE}🕐 Checking system status at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.ENDC}\n")
        
        # Check API health
        health_data = self.check_api_health()
        if health_data:
            self.print_health_status(health_data)
        else:
            print(f"{Colors.FAIL}❌ API server is not responding{Colors.ENDC}")
            return False
        
        # Get metrics
        metrics_data = self.get_system_metrics()
        if metrics_data:
            self.print_performance_metrics(metrics_data)
            self.print_recent_activity(metrics_data)
        
        # Service status
        self.print_service_status()
        
        print(f"\n{Colors.OKGREEN}{Colors.BOLD}🎉 Status check complete!{Colors.ENDC}")
        return True

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced RAG System Status Checker")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API server URL")
    parser.add_argument("--dashboard-url", default="http://localhost:8080", help="Dashboard URL")
    parser.add_argument("--watch", action="store_true", help="Watch mode (refresh every 30s)")
    
    args = parser.parse_args()
    
    checker = SystemStatusChecker(args.api_url, args.dashboard_url)
    
    if args.watch:
        print(f"{Colors.OKBLUE}👀 Watch mode enabled (refresh every 30s, Ctrl+C to stop){Colors.ENDC}\n")
        try:
            while True:
                checker.run_status_check()
                print(f"\n{Colors.OKBLUE}{'='*60}{Colors.ENDC}")
                time.sleep(30)
        except KeyboardInterrupt:
            print(f"\n{Colors.OKGREEN}👋 Watch mode stopped{Colors.ENDC}")
    else:
        checker.run_status_check()

if __name__ == "__main__":
    main()
