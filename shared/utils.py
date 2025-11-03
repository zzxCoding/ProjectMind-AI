#!/usr/bin/env python3
"""
通用工具函数
提供日志设置、参数解析、时间格式化等常用功能
"""

import sys
import json
import logging
import argparse
from datetime import datetime
from typing import Any, Dict, List, Optional
import colorlog

def setup_logging(level: str = "INFO", use_color: bool = True) -> logging.Logger:
    """
    设置彩色日志
    
    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
        use_color: 是否使用彩色输出
    
    Returns:
        配置好的logger对象
    """
    logger = logging.getLogger()
    
    if logger.handlers:
        logger.handlers.clear()
    
    logger.setLevel(getattr(logging, level.upper()))
    
    if use_color:
        formatter = colorlog.ColoredFormatter(
            '%(log_color)s%(asctime)s [%(levelname)s] %(message)s%(reset)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger

def parse_arguments(description: str = "Python脚本") -> argparse.ArgumentParser:
    """
    创建通用的参数解析器
    
    Args:
        description: 脚本描述
        
    Returns:
        配置好的ArgumentParser
    """
    parser = argparse.ArgumentParser(description=description)
    
    parser.add_argument(
        '--log-level', 
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='日志级别 (默认: INFO)'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        help='配置文件路径'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='干运行模式，不执行实际操作'
    )
    
    return parser

def format_timestamp(dt: Optional[datetime] = None, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    格式化时间戳
    
    Args:
        dt: datetime对象，默认为当前时间
        format_str: 格式化字符串
        
    Returns:
        格式化后的时间字符串
    """
    if dt is None:
        dt = datetime.now()
    return dt.strftime(format_str)

def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """
    安全的JSON解析
    
    Args:
        json_str: JSON字符串
        default: 解析失败时的默认值
        
    Returns:
        解析结果或默认值
    """
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default

def safe_json_dumps(obj: Any, default: str = "null") -> str:
    """
    安全的JSON序列化
    
    Args:
        obj: 要序列化的对象
        default: 序列化失败时的默认值
        
    Returns:
        JSON字符串
    """
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        return default

def chunks(lst: List[Any], n: int) -> List[List[Any]]:
    """
    将列表分割成指定大小的块
    
    Args:
        lst: 要分割的列表
        n: 每块的大小
        
    Yields:
        分割后的块
    """
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def validate_required_args(args: Dict[str, Any], required: List[str]) -> List[str]:
    """
    验证必需参数
    
    Args:
        args: 参数字典
        required: 必需参数列表
        
    Returns:
        缺失的参数列表
    """
    missing = []
    for key in required:
        if key not in args or args[key] is None:
            missing.append(key)
    return missing

def print_json(data: Any) -> None:
    """
    美观地打印JSON数据
    
    Args:
        data: 要打印的数据
    """
    print(safe_json_dumps(data))

def exit_with_error(message: str, code: int = 1) -> None:
    """
    打印错误信息并退出
    
    Args:
        message: 错误信息
        code: 退出码
    """
    logger = logging.getLogger()
    logger.error(message)
    sys.exit(code)

def exit_with_success(message: str = "操作完成") -> None:
    """
    打印成功信息并正常退出
    
    Args:
        message: 成功信息
    """
    logger = logging.getLogger()
    logger.info(message)
    sys.exit(0)

if __name__ == "__main__":
    # 测试工具函数
    logger = setup_logging()
    logger.info("测试日志输出")
    logger.warning("这是一个警告")
    logger.error("这是一个错误")
    
    print(f"当前时间: {format_timestamp()}")
    print(f"JSON测试: {safe_json_dumps({'test': '中文测试'})}")
    
    test_list = list(range(10))
    print(f"分块测试: {list(chunks(test_list, 3))}")