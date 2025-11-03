#!/usr/bin/env python3
"""
SonarQube API客户端
提供SonarQube的API访问封装，用于获取项目质量分析数据
"""

import os
import sys
import json
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional
from sonarqube import SonarQubeClient as SonarAPI

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
from shared.utils import setup_logging

class SonarQubeConfig:
    """SonarQube配置类"""
    
    def __init__(self, url: str = None, token: str = None, timeout: int = 30, verify_ssl: bool = True):
        """
        初始化配置
        
        Args:
            url: SonarQube服务器地址
            token: API访问令牌  
            timeout: 超时时间(秒)
            verify_ssl: 是否验证SSL证书
        """
        self.url = url or os.getenv('SONARQUBE_URL', 'http://localhost:9000')
        self.token = token or os.getenv('SONARQUBE_TOKEN', '')
        self.timeout = timeout or int(os.getenv('SONARQUBE_TIMEOUT', '30'))
        self.verify_ssl = verify_ssl if verify_ssl is not None else os.getenv('SONARQUBE_VERIFY_SSL', 'true').lower() == 'true'
        
        # 确保URL格式正确
        if not self.url.startswith(('http://', 'https://')):
            self.url = f'http://{self.url}'
        
        if not self.url.endswith('/'):
            self.url += '/'

def get_default_sonarqube_config() -> SonarQubeConfig:
    """获取默认配置"""
    return SonarQubeConfig()

class SonarQubeClient:
    """SonarQube API客户端"""
    
    def __init__(self, config: Optional[SonarQubeConfig] = None):
        """
        初始化客户端
        
        Args:
            config: SonarQube配置，为空则使用默认配置
        """
        self.config = config or get_default_sonarqube_config()
        self.logger = setup_logging()
        
        # 创建SonarQube API客户端
        try:
            self.sonar = SonarAPI(
                sonarqube_url=self.config.url,
                token=self.config.token,  # 使用token认证
                verify=self.config.verify_ssl,
                timeout=self.config.timeout
            )
            
            self.logger.info(f"SonarQube客户端初始化完成 - 服务器: {self.config.url}")
        except Exception as e:
            import traceback
            self.logger.error(f"SonarQube客户端初始化失败: {e}")
            self.logger.error(f"完整堆栈信息:\n{traceback.format_exc()}")
            raise
    
    def test_connection(self) -> bool:
        """测试连接"""
        try:
            self.logger.info("测试SonarQube连接...")
            # 使用server API获取系统信息
            if hasattr(self.sonar, 'server'):
                # 尝试获取服务器版本信息
                version_info = self.sonar.server.get_server_version()
                if version_info:
                    self.logger.info(f"SonarQube连接成功 - 版本: {version_info}")
                    return True
            
            # 如果server API不可用，尝试获取项目列表作为连接测试
            projects = self.sonar.projects.search_projects(ps=1)
            if projects is not None:
                self.logger.info("SonarQube连接成功")
                return True
            else:
                self.logger.error("SonarQube连接失败")
                return False
        except Exception as e:
            import traceback
            self.logger.error(f"测试连接失败: {e}")
            self.logger.error(f"完整堆栈信息:\n{traceback.format_exc()}")
            return False
    
    def get_project_info(self, project_key: str) -> Optional[Dict[str, Any]]:
        """
        获取项目信息
        
        Args:
            project_key: 项目标识符
            
        Returns:
            项目信息字典
        """
        try:
            projects = self.sonar.projects.search_projects(projects=project_key)
            if projects and projects.get('components'):
                project_info = projects['components'][0]
                return {
                    'key': project_info.get('key'),
                    'name': project_info.get('name'),
                    'qualifier': project_info.get('qualifier'),
                    'visibility': project_info.get('visibility'),
                    'lastAnalysisDate': project_info.get('lastAnalysisDate'),
                    'tags': project_info.get('tags', [])
                }
            return None
        except Exception as e:
            self.logger.error(f"获取项目信息失败: {e}")
            return None
    
    def get_project_issues(self, project_key: str, severities: List[str] = None, 
                          types: List[str] = None, statuses: List[str] = None,
                          page_size: int = 500, max_total: int = 10000) -> List[Dict[str, Any]]:
        """
        获取项目问题列表（支持大规模数据智能采样）
        
        Args:
            project_key: 项目标识符
            severities: 严重程度过滤 ['INFO', 'MINOR', 'MAJOR', 'CRITICAL', 'BLOCKER']
            types: 问题类型过滤 ['CODE_SMELL', 'BUG', 'VULNERABILITY'] (Community Edition不支持SECURITY_HOTSPOT) 
            statuses: 状态过滤 ['OPEN', 'CONFIRMED', 'REOPENED', 'RESOLVED', 'CLOSED']
            page_size: 每页大小
            max_total: 最大获取数量（超过时使用智能采样）
            
        Returns:
            问题列表（经过智能采样处理）
        """
        try:
            self.logger.info("=== 开始智能获取项目问题 ===")
            
            # 🔍 第一步：获取问题总数概览
            initial_response = self.sonar.issues.search_issues(
                componentKeys=project_key,
                severities=','.join(severities) if severities else None,
                types=','.join(types) if types else None,
                statuses=','.join(statuses) if statuses else None,
                ps=1  # 只获取1个用于检查总数
            )
            
            total_count = self._extract_total_count(initial_response)
            self.logger.info(f"📊 项目问题总数: {total_count}")
            
            # 🎯 第二步：决定采样策略
            if total_count <= max_total:
                # 数量可控，获取所有数据
                return self._get_all_issues(project_key, severities, types, statuses, total_count, page_size)
            else:
                # 数量过大，使用智能采样
                self.logger.warning(f"⚠️ 问题数量过大({total_count} > {max_total})，启用智能采样策略")
                return self._get_sampled_issues(project_key, severities, types, statuses, total_count, max_total)
                
        except Exception as e:
            import traceback
            self.logger.error(f"获取项目问题失败: {e}")
            self.logger.error(f"完整堆栈信息:\n{traceback.format_exc()}")
            return []
    
    def _extract_total_count(self, response) -> int:
        """提取API响应中的总数"""
        if isinstance(response, dict):
            return response.get('total', 0)
        else:
            responses = list(response)
            if responses and isinstance(responses[0], dict):
                return responses[0].get('total', 0)
        return 0
    
    def _get_all_issues(self, project_key: str, severities, types, statuses, total_count: int, page_size: int):
        """获取所有问题（分页处理）"""
        all_issues = []
        pages_needed = (total_count // page_size) + (1 if total_count % page_size > 0 else 0)
        
        self.logger.info(f"📄 需要获取 {pages_needed} 页数据")
        
        for page in range(1, min(pages_needed + 1, 21)):  # 最多20页，防止无限循环
            response = self.sonar.issues.search_issues(
                componentKeys=project_key,
                severities=','.join(severities) if severities else None,
                types=','.join(types) if types else None,
                statuses=','.join(statuses) if statuses else None,
                ps=page_size,
                p=page
            )
            
            issues = self._extract_issues_from_response(response)
            all_issues.extend(issues)
            
            self.logger.info(f"📥 第{page}页: 获取 {len(issues)} 个问题，累计 {len(all_issues)} 个")
            
            if len(issues) < page_size:  # 最后一页
                break
                
        return all_issues
    
    def _get_sampled_issues(self, project_key: str, severities, types, statuses, total_count: int, max_total: int):
        """智能采样获取问题"""
        self.logger.info(f"🎯 启用智能采样: {total_count} → {max_total}")
        
        # 🔥 优先级采样策略：
        # 1. 所有BLOCKER和CRITICAL (无限制)
        # 2. 30%的MAJOR问题 
        # 3. 10%的MINOR问题
        # 4. 5%的INFO和CODE_SMELL问题
        
        sampled_issues = []
        
        # 高优先级问题 - 全量获取
        for severity in ['BLOCKER', 'CRITICAL']:
            high_priority_issues = self._get_issues_by_severity(project_key, types, statuses, [severity])
            sampled_issues.extend(high_priority_issues)
            self.logger.info(f"🔴 获取所有{severity}问题: {len(high_priority_issues)}个")
        
        # 中优先级问题 - 30%采样
        major_issues = self._get_issues_by_severity(project_key, types, statuses, ['MAJOR'])
        major_sample_size = min(len(major_issues), max(int(len(major_issues) * 0.3), 50))
        major_sampled = self._stratified_sample(major_issues, major_sample_size)
        sampled_issues.extend(major_sampled)
        self.logger.info(f"🟡 MAJOR问题采样: {len(major_sampled)}/{len(major_issues)}个")
        
        # 低优先级问题 - 10%采样
        remaining_budget = max_total - len(sampled_issues)
        if remaining_budget > 0:
            minor_issues = self._get_issues_by_severity(project_key, types, statuses, ['MINOR', 'INFO'])
            minor_sample_size = min(len(minor_issues), max(int(len(minor_issues) * 0.1), remaining_budget))
            minor_sampled = self._stratified_sample(minor_issues, minor_sample_size)
            sampled_issues.extend(minor_sampled)
            self.logger.info(f"🟢 MINOR/INFO问题采样: {len(minor_sampled)}/{len(minor_issues)}个")
        
        self.logger.info(f"✅ 智能采样完成: {len(sampled_issues)}/{total_count} 个问题")
        return sampled_issues
    
    def _get_issues_by_severity(self, project_key: str, types, statuses, severities: list):
        """按严重程度获取问题"""
        response = self.sonar.issues.search_issues(
            componentKeys=project_key,
            severities=','.join(severities),
            types=','.join(types) if types else None,
            statuses=','.join(statuses) if statuses else None,
            ps=500
        )
        return self._extract_issues_from_response(response)
    
    def _stratified_sample(self, issues: list, sample_size: int):
        """分层采样 - 确保不同类型问题都有代表性"""
        if len(issues) <= sample_size:
            return issues
            
        # 按问题类型分组
        type_groups = {}
        for issue in issues:
            issue_type = issue.get('type', 'UNKNOWN')
            if issue_type not in type_groups:
                type_groups[issue_type] = []
            type_groups[issue_type].append(issue)
        
        # 按比例采样
        sampled = []
        remaining_sample = sample_size
        
        for issue_type, type_issues in type_groups.items():
            if remaining_sample <= 0:
                break
                
            # 计算该类型应该采样的数量
            type_ratio = len(type_issues) / len(issues)
            type_sample_size = max(1, int(sample_size * type_ratio))
            type_sample_size = min(type_sample_size, remaining_sample, len(type_issues))
            
            # 均匀采样
            step = len(type_issues) // type_sample_size if type_sample_size > 0 else 1
            type_sampled = type_issues[::max(1, step)][:type_sample_size]
            
            sampled.extend(type_sampled)
            remaining_sample -= len(type_sampled)
        
        return sampled[:sample_size]
    
    def _extract_issues_from_response(self, response):
        """从API响应中提取问题列表"""
        if isinstance(response, dict):
            return response.get('issues', [])
        else:
            responses = list(response)
            if responses and isinstance(responses[0], dict):
                return responses[0].get('issues', [])
            return responses if responses else []
    
    def get_project_measures(self, project_key: str, metrics: List[str] = None) -> Dict[str, Any]:
        """
        获取项目度量数据
        
        Args:
            project_key: 项目标识符
            metrics: 度量指标列表，为空则获取常用指标
            
        Returns:
            度量数据字典
        """
        try:
            if not metrics:
                # 常用质量指标
                metrics = [
                    'alert_status',          # 质量门状态
                    'bugs',                  # Bug数量
                    'vulnerabilities',       # 漏洞数量
                    'code_smells',          # 代码异味数量
                    'security_hotspots',    # 安全热点数量
                    'coverage',             # 测试覆盖率
                    'duplicated_lines_density',  # 重复代码密度
                    'ncloc',                # 代码行数
                    'complexity',           # 圈复杂度
                    'cognitive_complexity', # 认知复杂度
                    'sqale_index',         # 技术债务
                    'reliability_rating',   # 可靠性评级
                    'security_rating',     # 安全性评级
                    'sqale_rating'  # 可维护性评级（技术债务评级）
                ]
            
            # 使用python-sonarqube-api获取度量数据
            measures = self.sonar.measures.get_component_with_specified_measures(
                component=project_key,
                metricKeys=','.join(metrics)
            )
            
            if measures and measures.get('component'):
                measures_data = {}
                measure_list = measures['component'].get('measures', [])
                
                for measure in measure_list:
                    metric = measure.get('metric')
                    value = measure.get('value')
                    
                    # 尝试转换为数值类型
                    if value is not None:
                        try:
                            # 尝试转换为整数
                            if '.' not in str(value):
                                measures_data[metric] = int(value)
                            else:
                                measures_data[metric] = float(value)
                        except (ValueError, TypeError):
                            # 保持原始字符串值
                            measures_data[metric] = value
                
                return measures_data
            return {}
            
        except Exception as e:
            self.logger.error(f"获取项目度量数据失败: {e}")
            return {}
    
    def get_project_hotspots(self, project_key: str, statuses: List[str] = None) -> List[Dict[str, Any]]:
        """
        获取安全热点
        
        Args:
            project_key: 项目标识符  
            statuses: 状态过滤 ['TO_REVIEW', 'ACKNOWLEDGED', 'FIXED', 'SAFE']
            
        Returns:
            安全热点列表
        """
        # Community Edition 10.4.1不支持安全热点API
        self.logger.warning("Community Edition版本不支持安全热点功能")
        return []
    
    def get_quality_gate_status(self, project_key: str) -> Dict[str, Any]:
        """
        获取质量门状态（Community Edition兼容版本）
        
        Args:
            project_key: 项目标识符
            
        Returns:
            质量门状态信息
        """
        try:
            # 方法1: 尝试获取项目度量数据推断质量门状态
            self.logger.info("尝试获取项目度量数据以推断质量门状态...")
            
            # 基于测试结果，使用有效的度量指标
            measures = self.get_project_measures(project_key, [
                'alert_status', 'bugs', 'vulnerabilities', 'code_smells', 
                'coverage', 'duplicated_lines_density', 'security_hotspots',
                'reliability_rating', 'security_rating', 'sqale_rating'
            ])
            
            # 检查是否有alert_status（质量门状态）
            alert_status = measures.get('alert_status', 'UNKNOWN')
            
            if alert_status != 'UNKNOWN':
                # 成功获取到质量门状态
                status = 'OK' if alert_status == 'OK' else 'ERROR'
                self.logger.info(f"通过度量数据获取到质量门状态: {status}")
                return self._build_quality_gate_response(status, measures)
            
            # 方法2: 基于度量数据推断状态
            self.logger.info("基于度量数据推断质量门状态...")
            return self._infer_quality_gate_status(measures)
            
        except Exception as e:
            self.logger.error(f"获取质量门状态失败: {e}")
            return {
                'status': 'ERROR',
                'message': str(e)
            }
    
    def _build_quality_gate_response(self, status: str, measures: dict) -> dict:
        """构建质量门响应"""
        conditions = []
        
        # 基于实际度量数据构建条件
        bugs = measures.get('bugs', 0)
        vulnerabilities = measures.get('vulnerabilities', 0)
        code_smells = measures.get('code_smells', 0)
        security_hotspots = measures.get('security_hotspots', 0)
        coverage = measures.get('coverage', 0)
        duplicated = measures.get('duplicated_lines_density', 0)
        reliability_rating = measures.get('reliability_rating', '1')
        security_rating = measures.get('security_rating', '1')
        sqale_rating = measures.get('sqale_rating', '1')
        
        # 构建条件
        if bugs > 0:
            conditions.append({'status': 'ERROR' if bugs > 0 else 'OK', 'metric': 'bugs', 'value': bugs})
        if vulnerabilities > 0:
            conditions.append({'status': 'ERROR' if vulnerabilities > 0 else 'OK', 'metric': 'vulnerabilities', 'value': vulnerabilities})
        if security_hotspots > 10:
            conditions.append({'status': 'WARNING' if security_hotspots > 10 else 'OK', 'metric': 'security_hotspots', 'value': security_hotspots})
        if code_smells > 50:
            conditions.append({'status': 'WARNING' if code_smells > 50 else 'OK', 'metric': 'code_smells', 'value': code_smells})
        if coverage < 70:
            conditions.append({'status': 'WARNING' if coverage < 70 else 'OK', 'metric': 'coverage', 'value': coverage})
        if duplicated > 5:
            conditions.append({'status': 'WARNING' if duplicated > 5 else 'OK', 'metric': 'duplicated_lines_density', 'value': duplicated})
        if reliability_rating in ['3', '4', '5']:
            conditions.append({'status': 'ERROR' if reliability_rating in ['4', '5'] else 'WARNING', 'metric': 'reliability_rating', 'value': reliability_rating})
        if security_rating in ['3', '4', '5']:
            conditions.append({'status': 'ERROR' if security_rating in ['4', '5'] else 'WARNING', 'metric': 'security_rating', 'value': security_rating})
        if sqale_rating in ['3', '4', '5']:
            conditions.append({'status': 'WARNING' if sqale_rating in ['4', '5'] else 'OK', 'metric': 'sqale_rating', 'value': sqale_rating})
        
        return {
            'status': status,
            'conditions': conditions,
            'source': 'metrics_inference',
            'measures': measures
        }
    
    def _infer_quality_gate_status(self, measures: dict) -> dict:
        """基于度量数据推断质量门状态"""
        bugs = measures.get('bugs', 0)
        vulnerabilities = measures.get('vulnerabilities', 0)
        code_smells = measures.get('code_smells', 0)
        security_hotspots = measures.get('security_hotspots', 0)
        coverage = measures.get('coverage', 0)
        duplicated = measures.get('duplicated_lines_density', 0)
        reliability_rating = measures.get('reliability_rating', '1')
        security_rating = measures.get('security_rating', '1')
        
        # 简单的质量门规则
        has_critical_issues = bugs > 0 or vulnerabilities > 0
        has_security_issues = security_hotspots > 20
        has_maintainability_issues = code_smells > 50 or duplicated > 5
        has_coverage_issues = coverage < 70
        has_rating_issues = reliability_rating in ['4', '5'] or security_rating in ['4', '5']
        
        if has_critical_issues:
            status = 'ERROR'
        elif has_security_issues or has_rating_issues:
            status = 'ERROR'
        elif has_maintainability_issues or has_coverage_issues:
            status = 'WARNING'
        else:
            status = 'OK'
        
        return self._build_quality_gate_response(status, measures)
    
    def get_project_analyses(self, project_key: str, category: str = 'VERSION') -> List[Dict[str, Any]]:
        """
        获取项目分析历史
        
        Args:
            project_key: 项目标识符
            category: 分析类别
            
        Returns:
            分析历史列表
        """
        try:
            # 使用python-sonarqube-api获取项目分析历史
            analyses = self.sonar.project_analyses.search_project_analyses(
                project=project_key,
                category=category,
                ps=100
            )
            
            if analyses:
                return analyses.get('analyses', [])
            return []
            
        except Exception as e:
            self.logger.error(f"获取项目分析历史失败: {e}")
            return []

def main():
    """命令行测试入口"""
    parser = argparse.ArgumentParser(description='SonarQube客户端测试工具')
    parser.add_argument('--url', help='SonarQube服务器地址')
    parser.add_argument('--token', help='访问令牌')
    parser.add_argument('--project-key', help='测试项目标识符')
    parser.add_argument('--test', choices=['connection', 'project', 'issues', 'measures'], 
                       default='connection', help='测试类型')
    parser.add_argument('--log-level', default='INFO', help='日志级别')
    
    args = parser.parse_args()
    
    # 设置日志
    logger = setup_logging(args.log_level)
    
    try:
        # 创建配置
        config = SonarQubeConfig(url=args.url, token=args.token)
        
        # 创建客户端
        client = SonarQubeClient(config)
        
        if args.test == 'connection':
            # 测试连接
            success = client.test_connection()
            print(f"连接测试: {'成功' if success else '失败'}")
            
        elif args.test == 'project' and args.project_key:
            # 测试项目信息
            project_info = client.get_project_info(args.project_key)
            if project_info:
                print("项目信息:")
                print(json.dumps(project_info, indent=2, ensure_ascii=False))
            else:
                print("获取项目信息失败")
                
        elif args.test == 'issues' and args.project_key:
            # 测试问题获取
            issues = client.get_project_issues(args.project_key, 
                                             severities=['CRITICAL', 'BLOCKER'])
            print(f"获取到 {len(issues)} 个高严重性问题")
            if issues:
                print("问题示例:")
                print(json.dumps(issues[0], indent=2, ensure_ascii=False))
                
        elif args.test == 'measures' and args.project_key:
            # 测试度量获取
            measures = client.get_project_measures(args.project_key)
            if measures:
                print("项目度量:")
                print(json.dumps(measures, indent=2, ensure_ascii=False))
            else:
                print("获取项目度量失败")
        else:
            print("请提供必要的参数进行测试")
            
    except Exception as e:
        logger.error(f"测试失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()