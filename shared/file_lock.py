#!/usr/bin/env python3
"""
文件锁工具类
用于防止多个实例并发执行
"""

import os
import fcntl
import time
import tempfile
from typing import Optional, ContextManager
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

class FileLock:
    """文件锁工具类"""
    
    def __init__(self, lock_name: str, lock_dir: str = "/tmp"):
        """
        初始化文件锁
        
        Args:
            lock_name: 锁名称
            lock_dir: 锁文件目录
        """
        self.lock_name = lock_name
        self.lock_dir = lock_dir
        self.lock_file = None
        self.is_locked = False
        
    def acquire(self, timeout: int = 0, wait_interval: float = 1.0) -> bool:
        """
        获取文件锁
        
        Args:
            timeout: 超时时间（秒），0表示不等待，-1表示无限等待
            wait_interval: 等待间隔（秒）
            
        Returns:
            是否成功获取锁
        """
        lock_path = os.path.join(self.lock_dir, f"{self.lock_name}.lock")
        
        start_time = time.time()
        
        while True:
            try:
                # 创建锁文件
                self.lock_file = open(lock_path, 'w')
                
                # 尝试获取排他锁
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                
                # 写入进程信息
                pid = os.getpid()
                self.lock_file.write(f"PID: {pid}\nTime: {time.time()}\n")
                self.lock_file.flush()
                
                self.is_locked = True
                logger.info(f"成功获取锁: {self.lock_name} (PID: {pid})")
                return True
                
            except (IOError, BlockingIOError):
                # 锁已被占用
                if self.lock_file:
                    self.lock_file.close()
                    self.lock_file = None
                
                if timeout == 0:
                    # 不等待，直接返回失败
                    logger.debug(f"锁被占用，不等待: {self.lock_name}")
                    return False
                
                # 检查是否超时
                if timeout > 0 and (time.time() - start_time) >= timeout:
                    logger.warning(f"获取锁超时: {self.lock_name}")
                    return False
                
                # 等待一段时间后重试
                logger.debug(f"锁被占用，等待 {wait_interval} 秒后重试: {self.lock_name}")
                time.sleep(wait_interval)
                
            except Exception as e:
                logger.error(f"获取锁时发生异常: {self.lock_name} - {e}")
                if self.lock_file:
                    self.lock_file.close()
                    self.lock_file = None
                return False
    
    def release(self):
        """释放文件锁"""
        if self.lock_file and self.is_locked:
            try:
                # 释放锁
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
                self.lock_file.close()
                
                # 删除锁文件
                lock_path = os.path.join(self.lock_dir, f"{self.lock_name}.lock")
                if os.path.exists(lock_path):
                    os.unlink(lock_path)
                
                self.is_locked = False
                logger.info(f"成功释放锁: {self.lock_name}")
                
            except Exception as e:
                logger.error(f"释放锁时发生异常: {self.lock_name} - {e}")
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.release()
    
    def __del__(self):
        """析构函数"""
        self.release()

@contextmanager
def file_lock(lock_name: str, timeout: int = 0, wait_interval: float = 1.0) -> ContextManager[bool]:
    """
    文件锁上下文管理器
    
    Args:
        lock_name: 锁名称
        timeout: 超时时间（秒）
        wait_interval: 等待间隔（秒）
        
    Yields:
        是否成功获取锁
        
    Example:
        with file_lock("mr_review", timeout=30) as locked:
            if locked:
                # 执行需要锁保护的代码
                pass
            else:
                # 未获取到锁，跳过执行
                pass
    """
    lock = FileLock(lock_name)
    acquired = lock.acquire(timeout=timeout, wait_interval=wait_interval)
    
    try:
        yield acquired
    finally:
        if acquired:
            lock.release()

def is_locked(lock_name: str, lock_dir: str = "/tmp") -> bool:
    """
    检查锁是否被占用
    
    Args:
        lock_name: 锁名称
        lock_dir: 锁文件目录
        
    Returns:
        锁是否被占用
    """
    lock_path = os.path.join(lock_dir, f"{lock_name}.lock")
    
    if not os.path.exists(lock_path):
        return False
    
    try:
        # 尝试以非阻塞方式获取锁
        with open(lock_path, 'r') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            # 如果能获取到锁，说明之前没有锁
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            return False
    except (IOError, BlockingIOError):
        # 无法获取锁，说明锁被占用
        return True
    except Exception:
        # 发生异常，假设锁被占用
        return True