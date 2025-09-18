"""
System Monitoring and Metrics for RAG System
Provides performance monitoring, health checks, and system metrics
"""
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from collections import deque, defaultdict
import json

# Optional system monitoring
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from logger import logger, log_operation, log_performance

@dataclass
class SystemMetrics:
    """System performance metrics"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_usage_percent: float
    active_connections: int
    request_count: int
    error_count: int
    avg_response_time: float

@dataclass
class ComponentHealth:
    """Component health status"""
    name: str
    status: str  # "healthy", "degraded", "unhealthy"
    last_check: datetime
    error_message: Optional[str] = None
    response_time: Optional[float] = None

class SystemMonitor:
    """System monitoring and metrics collection"""
    
    def __init__(self, history_size: int = 1000):
        self.history_size = history_size
        self.metrics_history = deque(maxlen=history_size)
        self.component_health = {}
        self.request_times = deque(maxlen=1000)
        self.error_count = 0
        self.request_count = 0
        self._lock = threading.Lock()
        self._start_time = datetime.now()
        
        # Start background monitoring
        self._monitoring_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitoring_thread.start()
    
    def _monitor_loop(self):
        """Background monitoring loop"""
        while True:
            try:
                self._collect_metrics()
                time.sleep(30)  # Collect metrics every 30 seconds
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(60)  # Wait longer on error
    
    def _collect_metrics(self):
        """Collect system metrics"""
        try:
            # Calculate average response time
            avg_response_time = 0
            if self.request_times:
                avg_response_time = sum(self.request_times) / len(self.request_times)
            
            if PSUTIL_AVAILABLE:
                # System metrics with psutil
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                metrics = SystemMetrics(
                    timestamp=datetime.now(),
                    cpu_percent=cpu_percent,
                    memory_percent=memory.percent,
                    memory_used_mb=memory.used / (1024 * 1024),
                    disk_usage_percent=disk.percent,
                    active_connections=0,  # Would need to track this
                    request_count=self.request_count,
                    error_count=self.error_count,
                    avg_response_time=avg_response_time
                )
            else:
                # Basic metrics without psutil
                metrics = SystemMetrics(
                    timestamp=datetime.now(),
                    cpu_percent=0.0,
                    memory_percent=0.0,
                    memory_used_mb=0.0,
                    disk_usage_percent=0.0,
                    active_connections=0,
                    request_count=self.request_count,
                    error_count=self.error_count,
                    avg_response_time=avg_response_time
                )
            
            with self._lock:
                self.metrics_history.append(metrics)
            
            log_operation("system_metrics_collected", 
                         cpu_percent=metrics.cpu_percent,
                         memory_percent=metrics.memory_percent,
                         avg_response_time=avg_response_time)
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
    
    def record_request(self, response_time: float, is_error: bool = False):
        """Record a request and its response time"""
        with self._lock:
            self.request_times.append(response_time)
            self.request_count += 1
            if is_error:
                self.error_count += 1
    
    def check_component_health(self, name: str, check_func) -> ComponentHealth:
        """Check health of a component"""
        start_time = time.time()
        try:
            result = check_func()
            response_time = time.time() - start_time
            
            health = ComponentHealth(
                name=name,
                status="healthy" if result else "unhealthy",
                last_check=datetime.now(),
                response_time=response_time
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            health = ComponentHealth(
                name=name,
                status="unhealthy",
                last_check=datetime.now(),
                error_message=str(e),
                response_time=response_time
            )
        
        self.component_health[name] = health
        return health
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status"""
        with self._lock:
            latest_metrics = self.metrics_history[-1] if self.metrics_history else None
            
            # Determine overall health
            overall_status = "healthy"
            issues = []
            
            if latest_metrics:
                if latest_metrics.cpu_percent > 90:
                    overall_status = "degraded"
                    issues.append("High CPU usage")
                
                if latest_metrics.memory_percent > 90:
                    overall_status = "degraded"
                    issues.append("High memory usage")
                
                if latest_metrics.disk_usage_percent > 90:
                    overall_status = "degraded"
                    issues.append("High disk usage")
                
                if latest_metrics.avg_response_time > 5.0:
                    overall_status = "degraded"
                    issues.append("Slow response times")
            
            # Check component health
            unhealthy_components = [
                name for name, health in self.component_health.items()
                if health.status == "unhealthy"
            ]
            
            if unhealthy_components:
                overall_status = "degraded"
                issues.append(f"Unhealthy components: {', '.join(unhealthy_components)}")
            
            return {
                "overall_status": overall_status,
                "uptime_seconds": (datetime.now() - self._start_time).total_seconds(),
                "latest_metrics": asdict(latest_metrics) if latest_metrics else None,
                "component_health": {name: asdict(health) for name, health in self.component_health.items()},
                "issues": issues,
                "request_count": self.request_count,
                "error_count": self.error_count,
                "error_rate": self.error_count / max(self.request_count, 1) * 100
            }
    
    def get_metrics_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get metrics history for the specified time period"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with self._lock:
            return [
                asdict(metrics) for metrics in self.metrics_history
                if metrics.timestamp > cutoff_time
            ]
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary"""
        with self._lock:
            if not self.request_times:
                return {"message": "No requests recorded yet"}
            
            response_times = list(self.request_times)
            return {
                "total_requests": self.request_count,
                "total_errors": self.error_count,
                "error_rate_percent": self.error_count / max(self.request_count, 1) * 100,
                "avg_response_time": sum(response_times) / len(response_times),
                "min_response_time": min(response_times),
                "max_response_time": max(response_times),
                "p95_response_time": sorted(response_times)[int(len(response_times) * 0.95)],
                "p99_response_time": sorted(response_times)[int(len(response_times) * 0.99)]
            }

# Global system monitor instance
system_monitor = SystemMonitor()

# Health check functions for components
def check_pinecone_health():
    """Check Pinecone connection health"""
    try:
        from config import config
        from pinecone import Pinecone
        
        pc = Pinecone(api_key=config.pinecone_api_key)
        index = pc.Index(config.pinecone.index_name)
        stats = index.describe_index_stats()
        return stats is not None
    except Exception:
        return False

def check_llm_health():
    """Check LLM connection health"""
    try:
        from config import config
        from langchain.chat_models import init_chat_model
        
        llm = init_chat_model(
            config.llm.model,
            model_provider=config.llm.provider,
            temperature=0.1,
            max_tokens=10
        )
        # Simple test query
        response = llm.invoke("test")
        return response is not None
    except Exception:
        return False

def check_database_health():
    """Check database connection health"""
    try:
        from conversation_manager import conversation_manager
        conversations = conversation_manager.list_conversations(limit=1)
        return True
    except Exception:
        return False

# Export
__all__ = ['SystemMonitor', 'SystemMetrics', 'ComponentHealth', 'system_monitor']
