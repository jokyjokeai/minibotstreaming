#!/usr/bin/env python3
"""
Configuration des logs pour MiniBotPanel v2 - SYSTÈME ULTRA-DÉTAILLÉ
Système de logging centralisé avec debug complet pour tous les scripts
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
import json
import traceback
import inspect
import threading
import time
import functools

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# Configuration par défaut
DEFAULT_LOG_LEVEL = logging.DEBUG
DEFAULT_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(funcName)s() - %(message)s'
DEFAULT_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# Couleurs pour la console
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'

class UltraDetailedFormatter(logging.Formatter):
    """Formatter ultra-détaillé avec couleurs et métadonnées"""
    
    COLORS = {
        'DEBUG': Colors.BLUE,
        'INFO': Colors.GREEN,
        'WARNING': Colors.YELLOW,
        'ERROR': Colors.RED,
        'CRITICAL': Colors.RED + Colors.BOLD
    }
    
    def format(self, record):
        # Ajouter informations système
        if not hasattr(record, 'thread_name'):
            record.thread_name = threading.current_thread().name
        if not hasattr(record, 'process_id'):
            record.process_id = os.getpid()
        if not hasattr(record, 'memory_mb'):
            if PSUTIL_AVAILABLE:
                try:
                    process = psutil.Process()
                    record.memory_mb = round(process.memory_info().rss / 1024 / 1024, 1)
                except:
                    record.memory_mb = 0
            else:
                record.memory_mb = 0
        
        # Format étendu avec métadonnées
        color = self.COLORS.get(record.levelname, Colors.RESET)
        
        # Format ultra-détaillé
        formatted_time = self.formatTime(record, self.datefmt)
        
        detailed_format = (
            f"{color}[{formatted_time}]{Colors.RESET} "
            f"{Colors.CYAN}PID:{record.process_id}{Colors.RESET} "
            f"{Colors.PURPLE}MEM:{record.memory_mb}MB{Colors.RESET} "
            f"{Colors.WHITE}[{record.thread_name}]{Colors.RESET} "
            f"{color}{record.levelname:<8}{Colors.RESET} "
            f"{Colors.BLUE}{record.name}{Colors.RESET} "
            f"{Colors.YELLOW}{record.filename}:{record.lineno}{Colors.RESET} "
            f"{Colors.GREEN}{record.funcName}(){Colors.RESET} "
            f"- {record.getMessage()}"
        )
        
        return detailed_format

class PerformanceTracker:
    """Suivi des performances globales"""
    
    def __init__(self):
        self.function_stats = {}
        self.lock = threading.Lock()
    
    def record_function_call(self, func_name: str, duration: float, success: bool):
        with self.lock:
            if func_name not in self.function_stats:
                self.function_stats[func_name] = {
                    'total_calls': 0,
                    'total_time': 0.0,
                    'failures': 0,
                    'avg_time': 0.0,
                    'max_time': 0.0,
                    'min_time': float('inf')
                }
            
            stats = self.function_stats[func_name]
            stats['total_calls'] += 1
            stats['total_time'] += duration
            stats['avg_time'] = stats['total_time'] / stats['total_calls']
            stats['max_time'] = max(stats['max_time'], duration)
            stats['min_time'] = min(stats['min_time'], duration)
            
            if not success:
                stats['failures'] += 1
    
    def get_stats(self) -> dict:
        with self.lock:
            return dict(self.function_stats)

# Instance globale de tracking
performance_tracker = PerformanceTracker()

def setup_logging(
    name: str = "minibotpanel",
    log_level: int = DEFAULT_LOG_LEVEL,
    log_dir: str = None,
    console_output: bool = True,
    file_output: bool = True,
    max_file_size: int = 50 * 1024 * 1024,  # 50MB pour plus de logs
    backup_count: int = 10,  # Plus de fichiers de backup
    ultra_detailed: bool = True
) -> logging.Logger:
    """
    Configure le système de logging ultra-détaillé
    """
    
    # Déterminer le répertoire des logs
    if log_dir is None:
        project_root = Path(__file__).parent
        log_dir = project_root / "logs"
    else:
        log_dir = Path(log_dir)
    
    # Créer le répertoire s'il n'existe pas
    log_dir.mkdir(exist_ok=True)
    
    # Créer le logger
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # Éviter la duplication si déjà configuré
    if logger.handlers:
        return logger
    
    # Handler pour fichier principal avec rotation
    if file_output:
        log_file = log_dir / f"{name}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        
        # Format ultra-détaillé pour fichier (sans couleurs)
        if ultra_detailed:
            file_format = (
                '%(asctime)s - PID:%(process)d - [%(threadName)s] - '
                '%(levelname)-8s - %(name)s - %(filename)s:%(lineno)d - %(funcName)s() - %(message)s'
            )
        else:
            file_format = DEFAULT_LOG_FORMAT
            
        file_formatter = logging.Formatter(file_format, DEFAULT_DATE_FORMAT)
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(log_level)
        logger.addHandler(file_handler)
        
        # Handler séparé pour les erreurs
        error_file = log_dir / f"{name}_errors.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_file,
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        logger.addHandler(error_handler)
        
        # Handler pour debug ultra-détaillé
        debug_file = log_dir / f"{name}_debug.log"
        debug_handler = logging.handlers.RotatingFileHandler(
            debug_file,
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.setFormatter(file_formatter)
        logger.addHandler(debug_handler)
    
    # Handler pour console avec couleurs
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        if ultra_detailed:
            console_formatter = UltraDetailedFormatter()
        else:
            console_formatter = logging.Formatter(DEFAULT_LOG_FORMAT, DEFAULT_DATE_FORMAT)
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(log_level)
        logger.addHandler(console_handler)
    
    return logger

def get_logger(name: str = None, **kwargs) -> logging.Logger:
    """
    Obtient un logger configuré ultra-détaillé
    """
    if name is None:
        # Récupérer le nom du module appelant
        frame = sys._getframe(1)
        name = frame.f_globals.get('__name__', 'minibotpanel')
    
    # Si le logger principal n'est pas encore configuré, le faire
    main_logger = logging.getLogger("minibotpanel")
    if not main_logger.handlers:
        setup_logging("minibotpanel", **kwargs)
    
    # Retourner un logger enfant
    child_logger = logging.getLogger(f"minibotpanel.{name}")
    
    # Ajouter informations système à chaque log
    if PSUTIL_AVAILABLE:
        old_makeRecord = child_logger.makeRecord
        def makeRecord(*args, **kwargs):
            record = old_makeRecord(*args, **kwargs)
            try:
                process = psutil.Process()
                record.memory_mb = round(process.memory_info().rss / 1024 / 1024, 1)
            except:
                record.memory_mb = 0
            return record
        child_logger.makeRecord = makeRecord
    
    return child_logger

def log_exception(logger: logging.Logger, message: str = "Exception occurred", include_stack: bool = True):
    """Log une exception avec traceback complet et context"""
    exc_info = sys.exc_info()
    
    if include_stack:
        logger.error(f"{message}: {traceback.format_exc()}")
    else:
        logger.error(f"{message}: {exc_info[1]}")
    
    # Logger les variables locales du frame où l'erreur s'est produite
    if exc_info[2]:
        frame = exc_info[2].tb_frame
        try:
            logger.debug(f"Local variables at error: {frame.f_locals}")
        except:
            logger.debug("Could not log local variables")

def log_function_call(include_args: bool = True, include_result: bool = False, log_performance: bool = True):
    """Décorateur ultra-détaillé pour logger les appels de fonction"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            func_name = f"{func.__module__}.{func.__name__}"
            
            # Log d'entrée
            if include_args:
                args_str = f"args={args[:3]}{'...' if len(args) > 3 else ''}, kwargs={dict(list(kwargs.items())[:3])}"
                logger.debug(f"🔵 ENTER {func_name}({args_str})")
            else:
                logger.debug(f"🔵 ENTER {func_name}()")
            
            start_time = time.time() if log_performance else None
            success = True
            result = None
            
            try:
                result = func(*args, **kwargs)
                
                # Log de sortie
                if include_result and result is not None:
                    result_str = str(result)[:100] + ('...' if len(str(result)) > 100 else '')
                    logger.debug(f"🟢 EXIT {func_name}() -> {result_str}")
                else:
                    logger.debug(f"🟢 EXIT {func_name}()")
                
                return result
                
            except Exception as e:
                success = False
                logger.error(f"🔴 ERROR {func_name}() -> {type(e).__name__}: {e}")
                log_exception(logger, f"Error in {func_name}")
                raise
                
            finally:
                if log_performance and start_time:
                    duration = time.time() - start_time
                    performance_tracker.record_function_call(func_name, duration, success)
                    
                    if duration > 0.1:  # Log performance si > 100ms
                        logger.info(f"⏱️  PERF {func_name}() took {duration:.3f}s")
        
        return wrapper
    return decorator

def log_memory_usage(func):
    """Décorateur pour logger l'usage mémoire"""
    if not PSUTIL_AVAILABLE:
        return func
        
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        
        try:
            process = psutil.Process()
            mem_before = process.memory_info().rss / 1024 / 1024
            
            result = func(*args, **kwargs)
            
            mem_after = process.memory_info().rss / 1024 / 1024
            mem_diff = mem_after - mem_before
            
            if abs(mem_diff) > 10:  # Log si différence > 10MB
                logger.info(f"💾 MEMORY {func.__name__}(): {mem_before:.1f}MB -> {mem_after:.1f}MB ({mem_diff:+.1f}MB)")
            
            return result
            
        except Exception as e:
            logger.error(f"💾 MEMORY ERROR in {func.__name__}(): {e}")
            return func(*args, **kwargs)
    
    return wrapper

def log_system_info(logger: logging.Logger = None):
    """Log les informations système détaillées"""
    if logger is None:
        logger = get_logger("system")
    
    try:
        import platform
        
        logger.info("=" * 60)
        logger.info("🖥️  SYSTEM INFORMATION")
        logger.info("=" * 60)
        logger.info(f"Platform: {platform.platform()}")
        logger.info(f"Architecture: {platform.architecture()}")
        logger.info(f"Processor: {platform.processor()}")
        logger.info(f"Python: {platform.python_version()}")
        
        if PSUTIL_AVAILABLE:
            # Informations mémoire
            memory = psutil.virtual_memory()
            logger.info(f"Memory: {memory.total // (1024**3)}GB total, {memory.available // (1024**3)}GB available")
            
            # Informations disque
            disk = psutil.disk_usage('/')
            logger.info(f"Disk: {disk.total // (1024**3)}GB total, {disk.free // (1024**3)}GB free")
            
            # Informations processus
            process = psutil.Process()
            logger.info(f"Process PID: {process.pid}")
            logger.info(f"Process Memory: {process.memory_info().rss // (1024**2)}MB")
        
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Failed to log system info: {e}")

def get_performance_stats() -> dict:
    """Récupère les statistiques de performance"""
    return performance_tracker.get_stats()

def log_performance_summary(logger: logging.Logger = None):
    """Log un résumé des performances"""
    if logger is None:
        logger = get_logger("performance")
    
    stats = get_performance_stats()
    if not stats:
        return
    
    logger.info("=" * 60)
    logger.info("📊 PERFORMANCE SUMMARY")
    logger.info("=" * 60)
    
    for func_name, data in sorted(stats.items(), key=lambda x: x[1]['total_time'], reverse=True)[:10]:
        logger.info(
            f"🎯 {func_name}: "
            f"{data['total_calls']} calls, "
            f"avg: {data['avg_time']:.3f}s, "
            f"total: {data['total_time']:.3f}s, "
            f"failures: {data['failures']}"
        )
    
    logger.info("=" * 60)

# Fonction de compatibilité avec l'ancien système
def setup_logger(name: str, log_file: str = None, level=logging.DEBUG):
    """Fonction de compatibilité - utilise le nouveau système"""
    return get_logger(name)

# Configuration globale au module level avec ultra-détail
_main_logger = setup_logging(ultra_detailed=True)

# Export du logger principal
logger = _main_logger

# Log des informations système au démarrage
log_system_info(_main_logger)