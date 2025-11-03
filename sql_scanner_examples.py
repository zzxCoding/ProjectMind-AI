#!/usr/bin/env python3
"""
SQL扫描工具使用示例
展示如何使用自定义AI模型和参数
"""

import os
import sys

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from automation.sql_project_scanner import SQLProjectScanner

def main():
    """主函数"""
    print("SQL扫描工具使用示例")
    print("=" * 50)
    
    # 基本使用
    print("\n1. 基本使用（使用配置文件中的默认模型）:")
    print('python automation/sql_project_scanner.py --project-id 93 --version-path "v2.1.*" --branch "main"')
    
    # 自定义模型
    print("\n2. 使用自定义AI模型:")
    print('python automation/sql_project_scanner.py --project-id 93 --version-path "v2.1.*" --model "llama2:13b" --branch "main"')
    
    # 调整AI参数
    print("\n3. 调整AI参数:")
    print('python automation/sql_project_scanner.py --project-id 93 --version-path "v2.1.*" --temperature 0.3 --max-tokens 3000 --branch "main"')
    
    # 深度分析
    print("\n4. 深度分析:")
    print('python automation/sql_project_scanner.py --project-id 93 --version-path "v2.1.*" --analysis-depth deep --enable-thinking --branch "main"')
    
    # 快速检查
    print("\n5. 快速检查:")
    print('python automation/sql_project_scanner.py --project-id 93 --version-path "v2.1.*" --analysis-depth quick --branch "main"')
    
    # 自定义关注领域
    print("\n6. 自定义关注领域:")
    print('python automation/sql_project_scanner.py --project-id 93 --version-path "v2.1.*" --focus-areas "安全风险" "性能问题" --branch "main"')
    
    # 自定义指令
    print("\n7. 自定义分析指令:")
    print('python automation/sql_project_scanner.py --project-id 93 --version-path "v2.1.*" --custom-instructions "请特别关注事务处理和并发问题" --branch "main"')
    
    # 指定不同分支
    print("\n8. 指定不同分支:")
    print('python automation/sql_project_scanner.py --project-id 93 --version-path "v2.1.*" --branch "develop"')
    print('python automation/sql_project_scanner.py --project-id 93 --version-path "v2.1.*" --branch "feature/some-feature"')
    
    # 组合使用
    print("\n9. 组合使用（推荐）:")
    print('python automation/sql_project_scanner.py \\')
    print('  --project-id 93 \\')
    print('  --version-path "v2.1.*" \\')
    print('  --model "qwen:7b" \\')
    print('  --analysis-depth standard \\')
    print('  --focus-areas "安全风险" "性能问题" "语法错误" \\')
    print('  --branch "main" \\')
    print('  --output text')
    
    print("\n" + "=" * 50)
    print("使用建议:")
    print("- 日常快速检查: 使用 --analysis-depth quick")
    print("- 版本发布前检查: 使用 --analysis-depth deep")
    print("- 特定问题排查: 使用 --focus-areas 指定关注领域")
    print("- 性能优化分析: 使用自定义指令关注性能问题")
    print("- 安全审计: 重点关注安全风险领域")

if __name__ == "__main__":
    main()