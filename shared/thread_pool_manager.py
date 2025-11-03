#!/usr/bin/env python3
"""
线程池工具模块
提供多线程异步执行的功能
"""

import logging
from typing import List, Dict, Any, Callable, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from dataclasses import dataclass


@dataclass
class ThreadAnalysisResult:
    """线程分析结果"""
    success: bool
    result: Any = None
    error: str = None
    execution_time: float = 0.0
    file_path: str = ""


class ThreadPoolManager:
    """线程池管理器"""
    
    def __init__(self, max_workers: int = 3, logger: logging.Logger = None):
        """
        初始化线程池管理器
        
        Args:
            max_workers: 最大线程数
            logger: 日志记录器
        """
        self.max_workers = max_workers
        self.logger = logger or logging.getLogger(__name__)
    
    def execute_tasks(self, tasks: List[Tuple[Callable, tuple, dict]]) -> List[ThreadAnalysisResult]:
        """
        执行多个任务
        
        Args:
            tasks: 任务列表，每个任务是一个元组 (callable, args, kwargs)
            
        Returns:
            分析结果列表
        """
        results = []
        
        try:
            self.logger.info(f"开始使用 {self.max_workers} 个线程执行 {len(tasks)} 个任务")
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交所有任务
                future_to_task = {
                    executor.submit(self._execute_task_wrapper, func, args, kwargs, i): (func, i)
                    for i, (func, args, kwargs) in enumerate(tasks)
                }
                
                # 等待所有任务完成
                for future in as_completed(future_to_task):
                    func, task_index = future_to_task[future]
                    
                    try:
                        result = future.result()
                        results.append(result)
                        
                        if result.success:
                            self.logger.debug(f"任务 {task_index + 1} 执行成功，耗时 {result.execution_time:.2f}s")
                        else:
                            self.logger.warning(f"任务 {task_index + 1} 执行失败: {result.error}")
                            
                    except Exception as e:
                        error_result = ThreadAnalysisResult(
                            success=False,
                            error=f"任务执行异常: {str(e)}",
                            execution_time=0.0
                        )
                        results.append(error_result)
                        self.logger.error(f"任务 {task_index + 1} 执行异常: {e}")
            
            successful_tasks = sum(1 for r in results if r.success)
            self.logger.info(f"线程池执行完成: {successful_tasks}/{len(tasks)} 个任务成功")
            
        except Exception as e:
            self.logger.error(f"线程池执行失败: {e}")
            # 如果线程池失败，返回所有任务都失败的结果
            for i, (func, args, kwargs) in enumerate(tasks):
                error_result = ThreadAnalysisResult(
                    success=False,
                    error=f"线程池初始化失败: {str(e)}",
                    execution_time=0.0
                )
                results.append(error_result)
        
        return results
    
    def _execute_task_wrapper(self, func: Callable, args: tuple, kwargs: dict, task_index: int) -> ThreadAnalysisResult:
        """
        执行单个任务的包装器
        
        Args:
            func: 要执行的函数
            args: 函数参数
            kwargs: 函数关键字参数
            task_index: 任务索引
            
        Returns:
            分析结果
        """
        start_time = time.time()
        
        try:
            # 执行任务
            result = func(*args, **kwargs)
            
            execution_time = time.time() - start_time
            
            return ThreadAnalysisResult(
                success=True,
                result=result,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            return ThreadAnalysisResult(
                success=False,
                error=str(e),
                execution_time=execution_time
            )
    
    def analyze_files_concurrently(self, files_data: List[Dict[str, Any]], 
                                 analyze_func: Callable) -> Tuple[List[Any], List[Dict[str, Any]]]:
        """
        并发分析多个文件
        
        Args:
            files_data: 文件数据列表
            analyze_func: 分析函数
            
        Returns:
            (分析结果列表, 分析详情列表)
        """
        all_issues = []
        analysis_details = []
        
        # 准备任务
        tasks = []
        for i, file_data in enumerate(files_data):
            task_args = (file_data, i, len(files_data))
            tasks.append((analyze_func, task_args, {}))
        
        # 执行任务
        results = self.execute_tasks(tasks)
        
        # 处理结果
        for i, (file_data, result) in enumerate(zip(files_data, results)):
            file_path = file_data.get('new_path', file_data.get('old_path', ''))
            diff_size = len(file_data.get('diff', ''))
            
            if result.success:
                issues = result.result
                all_issues.extend(issues)
                
                analysis_detail = {
                    'path': file_path,
                    'size': diff_size,
                    'issues_count': len(issues),
                    'analysis_time': f"{result.execution_time:.2f}s",
                    'success': True
                }
            else:
                analysis_detail = {
                    'path': file_path,
                    'size': diff_size,
                    'issues_count': 0,
                    'analysis_time': f"{result.execution_time:.2f}s",
                    'success': False,
                    'error': result.error
                }
            
            analysis_details.append(analysis_detail)
        
        return all_issues, analysis_details