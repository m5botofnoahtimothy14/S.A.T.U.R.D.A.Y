# core/logging_config.py
"""
AEGIS Centralized Logging System
================================
Provides structured logging with separate log files for each module/component.
"""
import logging
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

LOG_SUBSYSTEMS = {
    "core": "logs/core",
    "deep_learning": "logs/deep_learning",
    "ml": "logs/ml",
    "identity": "logs/identity",
    "health": "logs/health",
    "governance": "logs/governance",
    "communication": "logs/communication",
    "embodied": "logs/embodied",
    "hybrid": "logs/hybrid",
    "homebot": "logs/homebot",
    "security": "logs/security",
    "ui": "logs/ui",
    "services": "logs/services",
    "distributed": "logs/distributed",
    "api": "logs/api",
    "system": "logs/system",
}

for subdir in LOG_SUBSYSTEMS.values():
    Path(subdir).mkdir(parents=True, exist_ok=True)

class AEGISLogger:
    _loggers = {}
    _handlers = {}
    
    @classmethod
    def get_logger(cls, name: str, subsystem: str = "core"):
        """Get a logger that writes to both main log and subsystem-specific log"""
        logger_name = f"AEGIS.{name}"
        
        if logger_name in cls._loggers:
            return cls._loggers[logger_name]
        
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        logger.handlers = []
        logger.propagate = False
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        json_formatter = logging.Formatter(
            '{"time":"%(asctime)s","logger":"%(name)s","level":"%(levelname)s","message":"%(message)s"}',
            datefmt='%Y-%m-%dT%H:%M:%S'
        )
        
        main_log_file = LOG_DIR / "aegis.log"
        main_handler = logging.FileHandler(main_log_file, encoding='utf-8')
        main_handler.setLevel(logging.DEBUG)
        main_handler.setFormatter(formatter)
        logger.addHandler(main_handler)
        
        if subsystem in LOG_SUBSYSTEMS:
            sub_log_file = Path(LOG_SUBSYSTEMS[subsystem]) / f"{subsystem}.log"
            sub_handler = logging.FileHandler(sub_log_file, encoding='utf-8')
            sub_handler.setLevel(logging.DEBUG)
            sub_handler.setFormatter(formatter)
            logger.addHandler(sub_handler)
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        cls._loggers[logger_name] = logger
        return logger
    
    @classmethod
    def get_structlogger(cls, name: str, subsystem: str = "core"):
        """Get a structlog logger that writes to subsystem log"""
        import structlog
        
        log_file = LOG_DIR / "aegis.log"
        if subsystem in LOG_SUBSYSTEMS:
            log_file = Path(LOG_SUBSYSTEMS[subsystem]) / f"{subsystem}.log"
        
        structlog.configure(
            processors=[
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.JSONRenderer()
            ],
            logger_factory=structlog.WriteLoggerFactory(file=open(log_file, "a", encoding='utf-8')),
            wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
        )
        
        return structlog.get_logger(f"AEGIS.{name}")

def setup_aegis_logging():
    """Initialize the main logging system"""
    main_log = LOG_DIR / "aegis.log"
    
    root_logger = logging.getLogger("AEGIS")
    if getattr(root_logger, "_aegis_configured", False):
        return root_logger
    
    root_logger.setLevel(logging.DEBUG)
    root_logger.propagate = False

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    has_main_file_handler = any(
        isinstance(h, logging.FileHandler) and Path(getattr(h, "baseFilename", "")).name == main_log.name
        for h in root_logger.handlers
    )
    if not has_main_file_handler:
        file_handler = logging.FileHandler(main_log, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    has_console_handler = any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        for h in root_logger.handlers
    )
    if not has_console_handler:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    root_logger._aegis_configured = True
    
    return root_logger

def get_log_file_path(subsystem: str = None) -> str:
    """Get the path to a log file"""
    if subsystem and subsystem in LOG_SUBSYSTEMS:
        return str(Path(LOG_SUBSYSTEMS[subsystem]) / f"{subsystem}.log")
    return str(LOG_DIR / "aegis.log")
