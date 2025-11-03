#!/usr/bin/env python3
"""
备份处理脚本
处理脚本文件、日志文件和数据库的备份操作
"""

import sys
import os
import shutil
import tarfile
import gzip
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import json

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from shared.config_loader import config, setup_environment
setup_environment()
from shared.utils import setup_logging, parse_arguments, format_timestamp, exit_with_error, exit_with_success
from shared.database_client import DatabaseClient

class BackupProcessor:
    """备份处理器"""
    
    def __init__(self, backup_base_dir: str = "/tmp/script_manager_backups"):
        self.logger = setup_logging()
        self.db_client = DatabaseClient()
        self.backup_base_dir = Path(backup_base_dir)
        self.backup_base_dir.mkdir(parents=True, exist_ok=True)
        
        # 备份配置（使用智能配置加载器）
        self.config = {
            'scripts_dir': config.get('SCRIPTS_DIR', '/app/scripts'),
            'logs_dir': config.get('LOGS_DIR', '/app/logs'),
            'backup_dir': config.get('BACKUP_DIR', str(self.backup_base_dir)),
            'retention_days': int(config.get('BACKUP_RETENTION_DAYS', 30)),
            'compress': config.get('BACKUP_COMPRESS', 'true').lower() == 'true'
        }
    
    def create_full_backup(self) -> Dict[str, Any]:
        """
        创建完整备份
        
        Returns:
            备份操作结果
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"full_backup_{timestamp}"
        backup_dir = self.backup_base_dir / backup_name
        
        self.logger.info(f"开始创建完整备份: {backup_name}")
        
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            result = {
                'backup_name': backup_name,
                'backup_path': str(backup_dir),
                'timestamp': format_timestamp(),
                'components': {}
            }
            
            # 备份脚本文件
            scripts_backup = self._backup_scripts(backup_dir / 'scripts')
            result['components']['scripts'] = scripts_backup
            
            # 备份日志文件
            logs_backup = self._backup_logs(backup_dir / 'logs')
            result['components']['logs'] = logs_backup
            
            # 备份数据库元数据
            db_backup = self._backup_database_metadata(backup_dir / 'database')
            result['components']['database'] = db_backup
            
            # 创建备份信息文件
            self._create_backup_info(backup_dir, result)
            
            # 压缩备份（如果启用）
            if self.config['compress']:
                compressed_path = self._compress_backup(backup_dir)
                result['compressed_path'] = compressed_path
                # 删除原始目录
                shutil.rmtree(backup_dir)
                result['backup_path'] = compressed_path
            
            # 清理旧备份
            self._cleanup_old_backups()
            
            self.logger.info(f"完整备份创建成功: {result['backup_path']}")
            return result
            
        except Exception as e:
            self.logger.error(f"完整备份失败: {e}")
            # 清理失败的备份
            if backup_dir.exists():
                shutil.rmtree(backup_dir, ignore_errors=True)
            return {'error': str(e)}
    
    def create_incremental_backup(self, since_hours: int = 24) -> Dict[str, Any]:
        """
        创建增量备份
        
        Args:
            since_hours: 备份最近几小时的变化
            
        Returns:
            备份操作结果
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"incremental_backup_{timestamp}"
        backup_dir = self.backup_base_dir / backup_name
        
        self.logger.info(f"开始创建增量备份: {backup_name}（最近{since_hours}小时）")
        
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            cutoff_time = datetime.now() - timedelta(hours=since_hours)
            
            result = {
                'backup_name': backup_name,
                'backup_path': str(backup_dir),
                'timestamp': format_timestamp(),
                'since_hours': since_hours,
                'components': {}
            }
            
            # 备份最近修改的脚本
            scripts_backup = self._backup_recent_scripts(backup_dir / 'scripts', cutoff_time)
            result['components']['scripts'] = scripts_backup
            
            # 备份最近的日志
            logs_backup = self._backup_recent_logs(backup_dir / 'logs', cutoff_time)
            result['components']['logs'] = logs_backup
            
            # 备份最近的执行记录
            db_backup = self._backup_recent_executions(backup_dir / 'database', cutoff_time)
            result['components']['database'] = db_backup
            
            # 创建备份信息文件
            self._create_backup_info(backup_dir, result)
            
            # 压缩备份
            if self.config['compress']:
                compressed_path = self._compress_backup(backup_dir)
                result['compressed_path'] = compressed_path
                shutil.rmtree(backup_dir)
                result['backup_path'] = compressed_path
            
            self.logger.info(f"增量备份创建成功: {result['backup_path']}")
            return result
            
        except Exception as e:
            self.logger.error(f"增量备份失败: {e}")
            if backup_dir.exists():
                shutil.rmtree(backup_dir, ignore_errors=True)
            return {'error': str(e)}
    
    def restore_backup(self, backup_path: str, restore_components: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        恢复备份
        
        Args:
            backup_path: 备份文件路径
            restore_components: 要恢复的组件列表，None表示恢复所有
            
        Returns:
            恢复操作结果
        """
        self.logger.info(f"开始恢复备份: {backup_path}")
        
        backup_path = Path(backup_path)
        if not backup_path.exists():
            return {'error': f'备份文件不存在: {backup_path}'}
        
        try:
            # 创建临时解压目录
            temp_dir = self.backup_base_dir / f"restore_temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # 解压备份文件
            if backup_path.suffix == '.gz':
                with tarfile.open(backup_path, 'r:gz') as tar:
                    tar.extractall(temp_dir)
            else:
                # 假设是目录
                shutil.copytree(backup_path, temp_dir / backup_path.name)
            
            # 找到解压后的备份目录
            extracted_dirs = [d for d in temp_dir.iterdir() if d.is_dir()]
            if not extracted_dirs:
                return {'error': '备份文件格式无效'}
            
            backup_dir = extracted_dirs[0]
            
            # 读取备份信息
            backup_info_path = backup_dir / 'backup_info.json'
            if backup_info_path.exists():
                with open(backup_info_path, 'r', encoding='utf-8') as f:
                    backup_info = json.load(f)
            else:
                backup_info = {}
            
            result = {
                'backup_path': str(backup_path),
                'restore_timestamp': format_timestamp(),
                'restored_components': {},
                'backup_info': backup_info
            }
            
            # 恢复各个组件
            components_to_restore = restore_components or ['scripts', 'logs', 'database']
            
            if 'scripts' in components_to_restore and (backup_dir / 'scripts').exists():
                scripts_result = self._restore_scripts(backup_dir / 'scripts')
                result['restored_components']['scripts'] = scripts_result
            
            if 'logs' in components_to_restore and (backup_dir / 'logs').exists():
                logs_result = self._restore_logs(backup_dir / 'logs')
                result['restored_components']['logs'] = logs_result
            
            if 'database' in components_to_restore and (backup_dir / 'database').exists():
                db_result = self._restore_database(backup_dir / 'database')
                result['restored_components']['database'] = db_result
            
            # 清理临时目录
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            self.logger.info("备份恢复完成")
            return result
            
        except Exception as e:
            self.logger.error(f"备份恢复失败: {e}")
            # 清理临时目录
            if 'temp_dir' in locals() and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
            return {'error': str(e)}
    
    def list_backups(self) -> Dict[str, Any]:
        """
        列出所有备份
        
        Returns:
            备份列表
        """
        backups = []
        
        # 扫描备份目录
        for item in self.backup_base_dir.iterdir():
            if item.is_file() and item.suffix == '.gz':
                # 压缩备份文件
                backup_info = {
                    'name': item.stem,
                    'path': str(item),
                    'type': 'compressed',
                    'size': item.stat().st_size,
                    'created_time': datetime.fromtimestamp(item.stat().st_ctime),
                    'modified_time': datetime.fromtimestamp(item.stat().st_mtime)
                }
                backups.append(backup_info)
            
            elif item.is_dir() and ('backup_' in item.name):
                # 目录形式的备份
                backup_info_path = item / 'backup_info.json'
                if backup_info_path.exists():
                    try:
                        with open(backup_info_path, 'r', encoding='utf-8') as f:
                            info = json.load(f)
                    except:
                        info = {}
                else:
                    info = {}
                
                backup_info = {
                    'name': item.name,
                    'path': str(item),
                    'type': 'directory',
                    'size': sum(f.stat().st_size for f in item.rglob('*') if f.is_file()),
                    'created_time': datetime.fromtimestamp(item.stat().st_ctime),
                    'modified_time': datetime.fromtimestamp(item.stat().st_mtime),
                    'info': info
                }
                backups.append(backup_info)
        
        # 按创建时间排序
        backups.sort(key=lambda x: x['created_time'], reverse=True)
        
        return {
            'total_backups': len(backups),
            'backups': backups,
            'total_size': sum(b['size'] for b in backups)
        }
    
    def _backup_scripts(self, backup_dir: Path) -> Dict[str, Any]:
        """备份脚本文件"""
        backup_dir.mkdir(parents=True, exist_ok=True)
        scripts_dir = Path(self.config['scripts_dir'])
        
        if not scripts_dir.exists():
            return {'status': 'skipped', 'reason': 'scripts directory not found'}
        
        backed_up_files = []
        
        for script_file in scripts_dir.rglob('*'):
            if script_file.is_file():
                relative_path = script_file.relative_to(scripts_dir)
                backup_file = backup_dir / relative_path
                backup_file.parent.mkdir(parents=True, exist_ok=True)
                
                shutil.copy2(script_file, backup_file)
                backed_up_files.append(str(relative_path))
        
        return {
            'status': 'completed',
            'files_backed_up': len(backed_up_files),
            'files': backed_up_files
        }
    
    def _backup_logs(self, backup_dir: Path) -> Dict[str, Any]:
        """备份日志文件"""
        backup_dir.mkdir(parents=True, exist_ok=True)
        logs_dir = Path(self.config['logs_dir'])
        
        if not logs_dir.exists():
            return {'status': 'skipped', 'reason': 'logs directory not found'}
        
        backed_up_files = []
        
        for log_file in logs_dir.rglob('*.log'):
            if log_file.is_file():
                relative_path = log_file.relative_to(logs_dir)
                backup_file = backup_dir / relative_path
                backup_file.parent.mkdir(parents=True, exist_ok=True)
                
                # 压缩日志文件
                with open(log_file, 'rb') as f_in:
                    with gzip.open(f"{backup_file}.gz", 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                backed_up_files.append(str(relative_path))
        
        return {
            'status': 'completed',
            'files_backed_up': len(backed_up_files),
            'files': backed_up_files,
            'compressed': True
        }
    
    def _backup_database_metadata(self, backup_dir: Path) -> Dict[str, Any]:
        """备份数据库元数据"""
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # 导出脚本元数据
            scripts = self.db_client.get_all_scripts()
            with open(backup_dir / 'scripts_metadata.json', 'w', encoding='utf-8') as f:
                json.dump(scripts, f, indent=2, ensure_ascii=False, default=str)
            
            # 导出执行历史（最近1000条）
            executions = self.db_client.get_recent_executions(1000)
            with open(backup_dir / 'executions_history.json', 'w', encoding='utf-8') as f:
                json.dump(executions, f, indent=2, ensure_ascii=False, default=str)
            
            # 导出定时任务
            scheduled_tasks = self.db_client.get_scheduled_tasks()
            with open(backup_dir / 'scheduled_tasks.json', 'w', encoding='utf-8') as f:
                json.dump(scheduled_tasks, f, indent=2, ensure_ascii=False, default=str)
            
            # 导出用户信息
            users = self.db_client.get_users()
            with open(backup_dir / 'users.json', 'w', encoding='utf-8') as f:
                json.dump(users, f, indent=2, ensure_ascii=False, default=str)
            
            return {
                'status': 'completed',
                'files_exported': 4,
                'scripts_count': len(scripts),
                'executions_count': len(executions),
                'tasks_count': len(scheduled_tasks),
                'users_count': len(users)
            }
            
        except Exception as e:
            return {'status': 'failed', 'error': str(e)}
    
    def _backup_recent_scripts(self, backup_dir: Path, cutoff_time: datetime) -> Dict[str, Any]:
        """备份最近修改的脚本"""
        backup_dir.mkdir(parents=True, exist_ok=True)
        scripts_dir = Path(self.config['scripts_dir'])
        
        if not scripts_dir.exists():
            return {'status': 'skipped', 'reason': 'scripts directory not found'}
        
        recent_files = []
        
        for script_file in scripts_dir.rglob('*'):
            if script_file.is_file():
                mtime = datetime.fromtimestamp(script_file.stat().st_mtime)
                if mtime > cutoff_time:
                    relative_path = script_file.relative_to(scripts_dir)
                    backup_file = backup_dir / relative_path
                    backup_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    shutil.copy2(script_file, backup_file)
                    recent_files.append(str(relative_path))
        
        return {
            'status': 'completed',
            'files_backed_up': len(recent_files),
            'files': recent_files,
            'cutoff_time': format_timestamp(cutoff_time)
        }
    
    def _backup_recent_logs(self, backup_dir: Path, cutoff_time: datetime) -> Dict[str, Any]:
        """备份最近的日志"""
        backup_dir.mkdir(parents=True, exist_ok=True)
        logs_dir = Path(self.config['logs_dir'])
        
        if not logs_dir.exists():
            return {'status': 'skipped', 'reason': 'logs directory not found'}
        
        recent_logs = []
        
        for log_file in logs_dir.rglob('*.log'):
            if log_file.is_file():
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if mtime > cutoff_time:
                    relative_path = log_file.relative_to(logs_dir)
                    backup_file = backup_dir / relative_path
                    backup_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    # 压缩日志文件
                    with open(log_file, 'rb') as f_in:
                        with gzip.open(f"{backup_file}.gz", 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    
                    recent_logs.append(str(relative_path))
        
        return {
            'status': 'completed',
            'files_backed_up': len(recent_logs),
            'files': recent_logs,
            'cutoff_time': format_timestamp(cutoff_time),
            'compressed': True
        }
    
    def _backup_recent_executions(self, backup_dir: Path, cutoff_time: datetime) -> Dict[str, Any]:
        """备份最近的执行记录"""
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # 获取最近的执行记录
            all_executions = self.db_client.get_recent_executions(2000)
            recent_executions = [
                e for e in all_executions 
                if e['start_time'] and e['start_time'] > cutoff_time
            ]
            
            with open(backup_dir / 'recent_executions.json', 'w', encoding='utf-8') as f:
                json.dump(recent_executions, f, indent=2, ensure_ascii=False, default=str)
            
            return {
                'status': 'completed',
                'executions_backed_up': len(recent_executions),
                'cutoff_time': format_timestamp(cutoff_time)
            }
            
        except Exception as e:
            return {'status': 'failed', 'error': str(e)}
    
    def _create_backup_info(self, backup_dir: Path, backup_result: Dict[str, Any]) -> None:
        """创建备份信息文件"""
        with open(backup_dir / 'backup_info.json', 'w', encoding='utf-8') as f:
            json.dump(backup_result, f, indent=2, ensure_ascii=False, default=str)
    
    def _compress_backup(self, backup_dir: Path) -> str:
        """压缩备份目录"""
        compressed_path = f"{backup_dir}.tar.gz"
        
        with tarfile.open(compressed_path, 'w:gz') as tar:
            tar.add(backup_dir, arcname=backup_dir.name)
        
        return compressed_path
    
    def _cleanup_old_backups(self) -> None:
        """清理旧备份"""
        cutoff_time = datetime.now() - timedelta(days=self.config['retention_days'])
        
        for item in self.backup_base_dir.iterdir():
            if item.stat().st_ctime < cutoff_time.timestamp():
                if item.is_file():
                    item.unlink()
                    self.logger.info(f"删除过期备份文件: {item}")
                elif item.is_dir():
                    shutil.rmtree(item)
                    self.logger.info(f"删除过期备份目录: {item}")
    
    def _restore_scripts(self, scripts_backup_dir: Path) -> Dict[str, Any]:
        """恢复脚本文件"""
        scripts_dir = Path(self.config['scripts_dir'])
        restored_files = []
        
        for backup_file in scripts_backup_dir.rglob('*'):
            if backup_file.is_file():
                relative_path = backup_file.relative_to(scripts_backup_dir)
                target_file = scripts_dir / relative_path
                target_file.parent.mkdir(parents=True, exist_ok=True)
                
                shutil.copy2(backup_file, target_file)
                restored_files.append(str(relative_path))
        
        return {
            'status': 'completed',
            'files_restored': len(restored_files),
            'files': restored_files
        }
    
    def _restore_logs(self, logs_backup_dir: Path) -> Dict[str, Any]:
        """恢复日志文件"""
        logs_dir = Path(self.config['logs_dir'])
        restored_files = []
        
        for backup_file in logs_backup_dir.rglob('*.gz'):
            if backup_file.is_file():
                relative_path = backup_file.relative_to(logs_backup_dir)
                # 移除.gz扩展名
                original_name = relative_path.with_suffix('').with_suffix('')
                target_file = logs_dir / original_name
                target_file.parent.mkdir(parents=True, exist_ok=True)
                
                # 解压缩日志文件
                with gzip.open(backup_file, 'rb') as f_in:
                    with open(target_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                restored_files.append(str(original_name))
        
        return {
            'status': 'completed',
            'files_restored': len(restored_files),
            'files': restored_files
        }
    
    def _restore_database(self, db_backup_dir: Path) -> Dict[str, Any]:
        """恢复数据库元数据"""
        restored_items = []
        
        # 这里只是示例，实际恢复数据库需要更谨慎的操作
        for json_file in db_backup_dir.glob('*.json'):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                restored_items.append({
                    'file': json_file.name,
                    'records': len(data) if isinstance(data, list) else 1
                })
            except Exception as e:
                restored_items.append({
                    'file': json_file.name,
                    'error': str(e)
                })
        
        return {
            'status': 'completed',
            'note': '数据库元数据已导出，请手动检查和导入',
            'files': restored_items
        }

def main():
    """主函数"""
    parser = parse_arguments("备份处理脚本")
    parser.add_argument('--action', choices=['backup', 'restore', 'list'], required=True, help='操作类型')
    parser.add_argument('--type', choices=['full', 'incremental'], default='incremental', help='备份类型')
    parser.add_argument('--backup-path', help='恢复时指定备份路径')
    parser.add_argument('--backup-dir', default='/tmp/script_manager_backups', help='备份根目录')
    parser.add_argument('--since-hours', type=int, default=24, help='增量备份的时间范围（小时）')
    parser.add_argument('--components', nargs='+', choices=['scripts', 'logs', 'database'], help='要恢复的组件')
    parser.add_argument('--output-format', choices=['json', 'text'], default='text', help='输出格式')
    
    args = parser.parse_args()
    
    # 设置日志级别
    logger = setup_logging(args.log_level)
    
    processor = BackupProcessor(args.backup_dir)
    
    try:
        if args.action == 'backup':
            if args.type == 'full':
                result = processor.create_full_backup()
            else:  # incremental
                result = processor.create_incremental_backup(args.since_hours)
        
        elif args.action == 'restore':
            if not args.backup_path:
                exit_with_error("恢复操作需要指定 --backup-path")
            result = processor.restore_backup(args.backup_path, args.components)
        
        elif args.action == 'list':
            result = processor.list_backups()
        
        else:
            exit_with_error("无效的操作类型")
        
        # 检查操作是否成功
        if 'error' in result:
            exit_with_error(f"操作失败: {result['error']}")
        
        # 输出结果
        if args.output_format == 'json':
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        else:
            # 文本格式输出
            if args.action == 'backup':
                print(f"=== 备份操作完成 ===")
                print(f"备份名称: {result.get('backup_name', 'N/A')}")
                print(f"备份路径: {result.get('backup_path', 'N/A')}")
                print(f"创建时间: {result.get('timestamp', 'N/A')}")
                
                components = result.get('components', {})
                for comp_name, comp_info in components.items():
                    if comp_info.get('status') == 'completed':
                        print(f"{comp_name}: {comp_info.get('files_backed_up', 0)} 个文件")
            
            elif args.action == 'restore':
                print(f"=== 恢复操作完成 ===")
                print(f"备份路径: {result.get('backup_path', 'N/A')}")
                print(f"恢复时间: {result.get('restore_timestamp', 'N/A')}")
                
                restored = result.get('restored_components', {})
                for comp_name, comp_info in restored.items():
                    if comp_info.get('status') == 'completed':
                        print(f"{comp_name}: {comp_info.get('files_restored', 0)} 个文件")
            
            elif args.action == 'list':
                print(f"=== 备份列表 ===")
                print(f"总备份数: {result.get('total_backups', 0)}")
                print(f"总大小: {result.get('total_size', 0) / (1024*1024):.2f} MB")
                
                for backup in result.get('backups', [])[:10]:  # 只显示前10个
                    size_mb = backup['size'] / (1024*1024)
                    print(f"  {backup['name']}: {size_mb:.2f} MB ({backup['created_time']})")
        
        exit_with_success()
        
    except Exception as e:
        exit_with_error(f"备份操作失败: {e}")

if __name__ == "__main__":
    main()