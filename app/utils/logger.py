"""
OCS网课助手日志配置
"""
import logging
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
        
        # 文件处理器 - 使用普通FileHandler，无大小限制
        file_handler = logging.FileHandler(
            log_file,
            encoding='utf-8',
            delay=True  # 延迟打开文件直到第一次写入
        )
        file_handler.setFormatter(formatter)
        
        # 控制台处理器
        try:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        except Exception:
            pass
        
        logger.addHandler(file_handler)
        
        return logger
        
    except Exception:
        return logging.getLogger(name)


# 创建全局日志记录器
logger = setup_logger()