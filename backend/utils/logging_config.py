"""
Logging Configuration for Agentic Travel Dashboard

Provides:
- Console + file logging (3 log files: all, warnings, errors)
- Raw/unformatted logging helpers
- JSON logging helpers
- Special dedicated loggers for specific activities (e.g., agent logs)

File location: backend/utils/logging_config.py
Log directory: AGENTIC_TRAVELQ/logs/
"""
import logging
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import json
from datetime import datetime, date


class ConditionalFormatter(logging.Formatter):
    """Formatter that can output raw or formatted messages"""
    
    def format(self, record):
        # Check if this record should be raw (unformatted)
        if getattr(record, 'raw', False):
            return record.getMessage()
        return super().format(record)


def get_project_root():
    """
    Get the project root directory dynamically
    
    This file is in: AGENTIC_TRAVELQ/backend/utils/logging_config.py
    Project root is 2 levels up: utils/ -> backend/ -> AGENTIC_TRAVELQ/
    """
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent
    return project_root


def get_log_dir():
    """Get log directory at project root"""
    return str(get_project_root() / "logs")


def setup_logging(
    log_file_name: str = "travel_dashboard", 
    log_dir: str = None, 
    console_level: int = logging.INFO,
    enable_console: bool = True,
    fresh_start: bool = False
):
    """
    Setup logging with console and file handlers
    
    Args:
        log_file_name: Base name for log files
        log_dir: Directory for log files (defaults to project_root/logs/)
        console_level: Logging level for console
        enable_console: Enable console output
        fresh_start: Delete old logs before starting
    """
    root = logging.getLogger()

    # Avoid duplicate handlers 
    if root.hasHandlers():
        root.handlers.clear()

    # Master control
    root.setLevel(logging.INFO)
    
    # === SILENCE NOISY THIRD-PARTY LOGGERS ===
    noisy_loggers = [
        'urllib3', 'urllib3.connectionpool',
        'httpcore.http11', 'httpcore.connection',
        'httpx',
        'asyncio',
        'uvicorn.access',  # Only show errors from uvicorn access logs
        'multipart.multipart',
    ]
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # Use ConditionalFormatter for all handlers
    formatter = ConditionalFormatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler - with UTF-8 encoding
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(console_level)
        console_handler.setFormatter(formatter)
        try:
            console_handler.stream = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
        except Exception:
            pass
        root.addHandler(console_handler)
    
    # Determine the full log directory path
    if log_dir is None:
        full_log_dir = get_log_dir()
    elif os.path.isabs(log_dir):
        full_log_dir = log_dir
    else:
        full_log_dir = str(get_project_root() / log_dir)
    
    # Ensure directory exists
    os.makedirs(full_log_dir, exist_ok=True)

    all_file_name = os.path.join(full_log_dir, f"{log_file_name}_all_messages.log")
    warning_file_name = os.path.join(full_log_dir, f"{log_file_name}_warnings.log")
    error_file_name = os.path.join(full_log_dir, f"{log_file_name}_errors.log")

    # Handle fresh_start - safe on Windows
    if fresh_start:
        for log_file in [all_file_name, warning_file_name, error_file_name]:
            if os.path.exists(log_file):
                try:
                    os.remove(log_file)
                except PermissionError:
                    print(f"⚠️  Log file locked (in use): {log_file}")
                    print(f"   Continuing with existing file...")
                except Exception as e:
                    print(f"⚠️  Could not delete {log_file}: {e}")
    
    # File handler 1 - all messages
    all_handler = logging.FileHandler(all_file_name, encoding='utf-8')
    all_handler.setLevel(logging.DEBUG)
    all_handler.setFormatter(formatter)
    root.addHandler(all_handler)
    
    # File handler 2 - warnings only
    warning_handler = logging.FileHandler(warning_file_name, encoding='utf-8')
    warning_handler.setLevel(logging.WARNING)
    warning_handler.setFormatter(formatter)
    root.addHandler(warning_handler)
    
    # File handler 3 - errors only
    error_handler = logging.FileHandler(error_file_name, encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root.addHandler(error_handler)


def shutdown_logging():
    """Flush and close all logging handlers."""
    logging.shutdown()


def setup_fresh_logging(
    log_file_name: str = "travel_dashboard", 
    log_dir: str = "logs", 
    console_level: int = logging.INFO,
    enable_console: bool = True
):
    """
    Setup fresh logging with deleted old files
    """
    # Ensure directory exists
    os.makedirs(log_dir, exist_ok=True)
    
    setup_logging(
        log_file_name=log_file_name, 
        log_dir=log_dir,
        console_level=console_level,
        enable_console=enable_console,
        fresh_start=True
    )


# ============================================================================
# HELPER FUNCTIONS FOR EASY RAW LOGGING
# ============================================================================

def log_raw(message, level=logging.INFO):
    """Log a raw (unformatted) message"""
    logger = logging.getLogger()
    safe_message = str(message).encode('utf-8', errors='replace').decode('utf-8')
    logger.log(level, safe_message, extra={'raw': True})


def log_debug_raw(message):
    log_raw(message, logging.DEBUG)


def log_info_raw(message):
    log_raw(message, logging.INFO)


def log_warning_raw(message):
    log_raw(message, logging.WARNING)


def log_error_raw(message):
    log_raw(message, logging.ERROR)


# ============================================================================
# JSON SERIALIZATION HELPER
# ============================================================================

def json_serializer(obj: Any) -> str:
    """Handle non-serializable objects for JSON logging"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, set):
        return list(obj)
    elif isinstance(obj, bytes):
        return obj.decode('utf-8', errors='replace')
    elif hasattr(obj, '__dict__'):
        return str(obj)
    return str(obj)


# ============================================================================
# JSON LOGGING HELPERS
# ============================================================================

def log_json_raw(
    data: Dict[str, Any],
    label: Optional[str] = None,
    indent: int = 2,
    level: int = logging.INFO,
    include_borders: bool = True
):
    """
    Log a dictionary/object as formatted JSON
    
    Args:
        data: Dictionary or object to log
        label: Optional label to print before JSON
        indent: JSON indentation (default: 2)
        level: Logging level (default: INFO)
        include_borders: Whether to include separator lines
    """
    logger = logging.getLogger()
    
    try:
        json_str = json.dumps(data, indent=indent, default=json_serializer, ensure_ascii=False)
        
        if include_borders:
            log_raw("=" * 70, level)
        
        if label:
            log_raw(f"📋 {label}", level)
            if include_borders:
                log_raw("=" * 70, level)
        
        log_raw(json_str, level)
        
        if include_borders:
            log_raw("=" * 70, level)
            
    except Exception as e:
        log_raw(f"❌ Error serializing JSON: {e}", logging.ERROR)
        log_raw(f"Data: {str(data)[:500]}...", logging.ERROR)


def log_json_compact(
    data: Dict[str, Any],
    label: Optional[str] = None,
    level: int = logging.INFO
):
    """
    Log a dictionary as compact JSON (no indentation)
    
    Args:
        data: Dictionary to log
        label: Optional label
        level: Logging level
    """
    try:
        json_str = json.dumps(data, default=json_serializer, ensure_ascii=False)
        
        if label:
            log_raw(f"{label}: {json_str}", level)
        else:
            log_raw(json_str, level)
            
    except Exception as e:
        log_raw(f"❌ Error serializing JSON: {e}", logging.ERROR)


# ============================================================================
# SPECIAL LOGGING FOR AGENTS
# ============================================================================

def setup_agent_logging(
    agent_name: str,
    fresh_start: bool = False
):
    """
    Setup dedicated logger for a specific agent
    
    Args:
        agent_name: Name of the agent (e.g., "flight_agent", "weather_agent")
        fresh_start: If True, delete existing log file
        
    Returns:
        Logger instance
    """
    logger_name = f"agent.{agent_name}"
    agent_logger = logging.getLogger(logger_name)
    
    # Skip if already configured
    if agent_logger.handlers:
        return agent_logger
    
    agent_logger.setLevel(logging.INFO)
    agent_logger.propagate = False
    
    formatter = ConditionalFormatter(
        "[%(asctime)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # File handler
    full_log_dir = get_log_dir()
    agent_log_dir = os.path.join(full_log_dir, "agents")
    os.makedirs(agent_log_dir, exist_ok=True)
    
    agent_file = os.path.join(agent_log_dir, f"{agent_name}.log")
    
    if fresh_start and os.path.exists(agent_file):
        try:
            os.remove(agent_file)
        except PermissionError:
            print(f"⚠️  Agent log file locked: {agent_file}")
        except Exception as e:
            print(f"⚠️  Could not delete agent log: {e}")
    
    agent_handler = logging.FileHandler(agent_file, encoding='utf-8')
    agent_handler.setLevel(logging.INFO)
    agent_handler.setFormatter(formatter)
    agent_logger.addHandler(agent_handler)
    
    return agent_logger


def log_agent_raw(
    message,
    agent_name: str,
    level: int = logging.INFO
):
    """
    Log raw message to agent-specific log
    
    Args:
        message: Message to log
        agent_name: Name of the agent
        level: Logging level
    """
    logger = logging.getLogger(f"agent.{agent_name}")
    safe_message = str(message).encode('utf-8', errors='replace').decode('utf-8')
    logger.log(level, safe_message, extra={'raw': True})


def log_agent_json(
    data: Dict[str, Any],
    agent_name: str,
    label: Optional[str] = None,
    indent: int = 2
):
    """
    Log JSON to agent-specific log
    
    Args:
        data: Dictionary to log
        agent_name: Name of the agent
        label: Optional label
        indent: JSON indentation
    """
    logger = logging.getLogger(f"agent.{agent_name}")
    
    try:
        json_str = json.dumps(data, indent=indent, default=json_serializer, ensure_ascii=False)
        safe_json = json_str.encode('utf-8', errors='replace').decode('utf-8')
        
        if label:
            logger.info(f"📋 {label}", extra={'raw': True})
        
        logger.info(safe_json, extra={'raw': True})
        
    except Exception as e:
        logger.error(f"❌ Error serializing JSON: {e}", extra={'raw': True})