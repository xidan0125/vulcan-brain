"""
KPI计算模型
"""
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from .task import Task, TaskStatus


class ProjectKPI(BaseModel):
    """项目KPI指标"""
    project_id: str
    calculated_at: str
    
    # 核心KPI
    task_completion_rate: float = 0       # 任务完成率 (已完成/总数)
    on_time_delivery_rate: float = 0      # 准时交付率 (按时完成/已完成)
    blocked_count: int = 0                # 当前阻塞数
    overdue_count: int = 0                # 当前逾期数
    
    # 汇报KPI
    report_rate: float = 0                # 汇报率 (有汇报的任务/应汇报的任务)
    avg_report_delay_hours: float = 0     # 平均汇报延迟(小时)
    
    # 进度KPI
    planned_progress: float = 0           # 计划进度 (按时间线)
    actual_progress: float = 0            # 实际进度 (任务完成)
    progress_deviation: float = 0         # 进度偏差 (实际-计划)
    
    # 风险KPI
    risk_score: float = 0                 # 风险评分 0-100 (越低越好)
    health_score: float = 100             # 健康度 0-100 (越高越好)
    
    # 任务统计
    total_tasks: int = 0
    pending_tasks: int = 0
    in_progress_tasks: int = 0
    completed_tasks: int = 0
    blocked_tasks: int = 0
    overdue_tasks: int = 0


def calculate_project_kpi(project_id: str, tasks: List[Task], reports_count: int = 0) -> ProjectKPI:
    """
    计算项目KPI
    
    Args:
        project_id: 项目ID
        tasks: 项目下所有任务
        reports_count: 汇报数量
    
    Returns:
        ProjectKPI对象
    """
    kpi = ProjectKPI(
        project_id=project_id,
        calculated_at=datetime.now().isoformat()
    )
    
    if not tasks:
        return kpi
    
    # 任务统计
    kpi.total_tasks = len(tasks)
    kpi.pending_tasks = sum(1 for t in tasks if t.status == TaskStatus.PENDING)
    kpi.in_progress_tasks = sum(1 for t in tasks if t.status == TaskStatus.IN_PROGRESS)
    kpi.completed_tasks = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
    kpi.blocked_tasks = sum(1 for t in tasks if t.status == TaskStatus.BLOCKED)
    kpi.overdue_tasks = sum(1 for t in tasks if t.status == TaskStatus.OVERDUE or t.is_overdue())
    
    kpi.blocked_count = kpi.blocked_tasks
    kpi.overdue_count = kpi.overdue_tasks
    
    # 任务完成率
    kpi.task_completion_rate = (kpi.completed_tasks / kpi.total_tasks) * 100
    
    # 准时交付率 (已完成任务中，按时完成的比例)
    completed_tasks = [t for t in tasks if t.status == TaskStatus.COMPLETED]
    if completed_tasks:
        on_time_count = sum(1 for t in completed_tasks 
                          if t.deadline and t.completed_at and t.completed_at <= t.deadline)
        kpi.on_time_delivery_rate = (on_time_count / len(completed_tasks)) * 100
    
    # 实际进度 (加权平均)
    total_progress = sum(t.progress for t in tasks)
    kpi.actual_progress = total_progress / kpi.total_tasks
    
    # 汇报率
    tasks_needing_report = [t for t in tasks if t.status in [TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED]]
    if tasks_needing_report:
        kpi.report_rate = min(100, (reports_count / len(tasks_needing_report)) * 100)
    
    # 风险评分计算
    # 风险因子: 逾期(权重40) + 阻塞(权重30) + 进度落后(权重30)
    overdue_factor = (kpi.overdue_tasks / kpi.total_tasks) * 40
    blocked_factor = (kpi.blocked_tasks / kpi.total_tasks) * 30
    
    # 进度落后: 如果有DDL，计算应该完成多少
    # 简化: 用已开始但未完成的任务进度来估算
    in_progress_tasks = [t for t in tasks if t.status == TaskStatus.IN_PROGRESS]
    if in_progress_tasks:
        avg_progress = sum(t.progress for t in in_progress_tasks) / len(in_progress_tasks)
        # 假设进行中的任务平均应该完成50%
        progress_lag = max(0, (50 - avg_progress) / 50) * 30
    else:
        progress_lag = 0
    
    kpi.risk_score = min(100, overdue_factor + blocked_factor + progress_lag)
    kpi.health_score = 100 - kpi.risk_score
    
    return kpi
