#!/usr/bin/env python3
"""
项目路径配置
自动检测项目根目录，避免硬编码路径
"""

import os
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.absolute()

# 添加项目根目录到Python路径
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 各模块路径
CONFIG_DIR = PROJECT_ROOT / "config"
SHARED_DIR = PROJECT_ROOT / "shared"
DATA_ANALYSIS_DIR = PROJECT_ROOT / "data_analysis"
AUTOMATION_DIR = PROJECT_ROOT / "automation"
SERVICES_DIR = PROJECT_ROOT / "services"

# 数据路径
LOGS_DIR = PROJECT_ROOT.parent / "logs"
SCRIPTS_DIR = PROJECT_ROOT.parent / "scripts"
BACKUPS_DIR = PROJECT_ROOT / "backups"
REPORTS_DIR = PROJECT_ROOT / "reports"
TEMP_DIR = PROJECT_ROOT / "temp"

# 确保目录存在
for directory in [BACKUPS_DIR, REPORTS_DIR, TEMP_DIR]:
    directory.mkdir(exist_ok=True)

def get_project_root():
    """获取项目根目录"""
    return PROJECT_ROOT

def get_data_path(relative_path=""):
    """获取数据文件路径"""
    if relative_path.startswith('/'):
        # 绝对路径，直接返回
        return Path(relative_path)
    else:
        # 相对于项目根目录的路径
        return PROJECT_ROOT / relative_path

def get_log_path(log_name=""):
    """获取日志文件路径"""
    if not log_name:
        return LOGS_DIR
    return LOGS_DIR / log_name

def setup_python_path():
    """设置Python路径"""
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

# 自动执行路径设置
setup_python_path()

if __name__ == "__main__":
    print(f"项目根目录: {PROJECT_ROOT}")
    print(f"配置目录: {CONFIG_DIR}")
    print(f"共享目录: {SHARED_DIR}")
    print(f"日志目录: {LOGS_DIR}")
    print(f"脚本目录: {SCRIPTS_DIR}")
