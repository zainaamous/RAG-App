"""
Enhanced Logging System for RAG Application
Provides structured logging with different levels and outputs
"""
import logging
import logging.handlers
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

@dataclass
class LogConfig:
    """Configuration for logging"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: Optional[str] = "logs/rag.log"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    console_output: bool = True
    json_format: bool = False

class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logging"""
    
    def format(self, record):
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add extra fields if present
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, default=str)

class RAGLogger:
    """Enhanced logger for RAG application"""
    
    def __init__(self, name: str = "rag", config: Optional[LogConfig] = None):
        self.name = name
        self.config = config or LogConfig()
        self.logger = self._setup_logger()
    
    def _setup_logger(self) -> logging.Logger:
        """Setup logger with file and console handlers"""
        logger = logging.getLogger(self.name)
        logger.setLevel(getattr(logging, self.config.level.upper()))
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # File handler with rotation
        if self.config.file_path:
            self._setup_file_handler(logger)
        
        # Console handler
        if self.config.console_output:
            self._setup_console_handler(logger)
        
        return logger
    
    def _setup_file_handler(self, logger: logging.Logger):
        """Setup file handler with rotation"""
        log_path = Path(self.config.file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=self.config.max_file_size,
            backupCount=self.config.backup_count
        )
        
        if self.config.json_format:
            formatter = StructuredFormatter()
        else:
            formatter = logging.Formatter(self.config.format)
        
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    def _setup_console_handler(self, logger: logging.Logger):
        """Setup console handler"""
        console_handler = logging.StreamHandler(sys.stdout)
        
        if self.config.json_format:
            formatter = StructuredFormatter()
        else:
            # Color formatter for console
            class ColorFormatter(logging.Formatter):
                COLORS = {
                    'DEBUG': '\033[36m',    # Cyan
                    'INFO': '\033[32m',     # Green
                    'WARNING': '\033[33m',  # Yellow
                    'ERROR': '\033[31m',    # Red
                    'CRITICAL': '\033[35m', # Magenta
                }
                RESET = '\033[0m'
                
                def format(self, record):
                    color = self.COLORS.get(record.levelname, '')
                    record.levelname = f"{color}{record.levelname}{self.RESET}"
                    return super().format(record)
            
            formatter = ColorFormatter(self.config.format)
        
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with extra fields"""
        self._log(logging.DEBUG, message, kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message with extra fields"""
        self._log(logging.INFO, message, kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with extra fields"""
        self._log(logging.WARNING, message, kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message with extra fields"""
        self._log(logging.ERROR, message, kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message with extra fields"""
        self._log(logging.CRITICAL, message, kwargs)
    
    def _log(self, level: int, message: str, extra_fields: Dict[str, Any]):
        """Internal logging method with extra fields"""
        if extra_fields:
            # Create a new record with extra fields
            record = self.logger.makeRecord(
                self.logger.name, level, "", 0, message, (), None
            )
            record.extra_fields = extra_fields
            self.logger.handle(record)
        else:
            self.logger.log(level, message)
    
    def log_operation(self, operation: str, **kwargs):
        """Log an operation with structured data"""
        self.info(f"Operation: {operation}", operation=operation, **kwargs)
    
    def log_performance(self, operation: str, duration: float, **kwargs):
        """Log performance metrics"""
        self.info(
            f"Performance: {operation} took {duration:.2f}s",
            operation=operation,
            duration=duration,
            **kwargs
        )
    
    def log_error(self, error: Exception, context: str = "", **kwargs):
        """Log error with context"""
        self.error(
            f"Error in {context}: {str(error)}",
            error_type=type(error).__name__,
            context=context,
            **kwargs,
            exc_info=True
        )

# Global logger instance
logger = RAGLogger()

# Convenience functions
def debug(message: str, **kwargs):
    logger.debug(message, **kwargs)

def info(message: str, **kwargs):
    logger.info(message, **kwargs)

def warning(message: str, **kwargs):
    logger.warning(message, **kwargs)

def error(message: str, **kwargs):
    logger.error(message, **kwargs)

def critical(message: str, **kwargs):
    logger.critical(message, **kwargs)

def log_operation(operation: str, **kwargs):
    logger.log_operation(operation, **kwargs)

def log_performance(operation: str, duration: float, **kwargs):
    logger.log_performance(operation, duration, **kwargs)

def log_error(error: Exception, context: str = "", **kwargs):
    logger.log_error(error, context, **kwargs)

# Export
__all__ = [
    'RAGLogger', 'LogConfig', 'logger',
    'debug', 'info', 'warning', 'error', 'critical',
    'log_operation', 'log_performance', 'log_error'
]
