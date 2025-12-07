"""
OCS网课助手日志配置
"""
import logging
import logging.handlers
import os
import sys
from pathlib import Path
from app.core.config import settings


def setup_logger(name: str = "ocs_api", log_file: str = None, level: str = None) -> logging.Logger:
    """
    设置日志记录器
    """
    # 检查Python是否正在关闭
    if hasattr(sys, 'meta_path') and sys.meta_path is None:
        # Python正在关闭，返回一个简单的logger
        return logging.getLogger(name)
    
    try:
        # 使用配置中的值，如果没有指定则使用默认值
        log_file = log_file or settings.LOG_FILE_PATH
        level = level or settings.LOG_LEVEL
        
        # 解析日志级别
        level = getattr(logging, level.upper(), logging.INFO)
        
        # 创建日志目录
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 创建logger
        logger = logging.getLogger(name)
        logger.setLevel(level)
        
        # 避免重复添加处理器
        if logger.handlers:
            logger.handlers.clear()
        
        # 创建格式器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # 文件处理器 - 使用RotatingFileHandler实现日志轮转
        max_bytes = settings.LOG_MAX_SIZE
        if max_bytes.endswith('MB'):
            max_bytes = int(max_bytes[:-2]) * 1024 * 1024
        elif max_bytes.endswith('KB'):
            max_bytes = int(max_bytes[:-2]) * 1024
        else:
            max_bytes = int(max_bytes)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=settings.LOG_BACKUP_COUNT,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        
        # 控制台处理器 - 添加错误处理
        try:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        except Exception:
            # 如果控制台处理器创建失败，只使用文件处理器
            pass
        
        logger.addHandler(file_handler)
        
        return logger
        
    except Exception:
        # 如果日志设置失败，返回基本logger
        return logging.getLogger(name)


# 创建全局日志记录器
logger = setup_logger()