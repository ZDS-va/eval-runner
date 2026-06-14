import datetime

from typing import Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.schemas.runner import CreateTaskResponse, EvalTaskRequest, ValidateResponse, BadCasesResponse
from app.services.runner import RunnerService


router = APIRouter()


@router.get("/health")
def health():
    """14.4 GET /runner/health 健康检查"""
    return {
        "status": "UP",
        "evalscope_available": True,
        "version": "0.1.0",
        "work_dir": "result",  # 默认的 MVP 输出目录
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }


@router.post("/eval-tasks/validate", response_model=ValidateResponse)
def validate_task(req: EvalTaskRequest):
    """14.6 POST /runner/eval-tasks/validate 校验配置"""
    result = RunnerService.validate_config(req)
    return result


@router.post("/eval-tasks", response_model=CreateTaskResponse)
def create_task(req: EvalTaskRequest, background_tasks: BackgroundTasks):
    """14.7 POST /runner/eval-tasks 创建并启动评测任务"""
    task_id = RunnerService.create_task(req, background_tasks)
    task_info = RunnerService.get_task(task_id)
    return {
        "task_id": task_id,
        "status": task_info["status"],
        "work_dir": task_info["work_dir"],
        "created_at": task_info["created_at"]
    }


@router.get("/eval-tasks/{task_id}")
def get_task(task_id: str):
    """14.8 GET /runner/eval-tasks/{task_id} 查询任务基本状态"""
    task_info = RunnerService.get_task(task_id)
    if not task_info:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {
        "task_id": task_info["task_id"],
        "status": task_info["status"],
        "model_service_id": task_info["model_service_id"],
        "dataset": task_info["dataset"],
        "work_dir": task_info["work_dir"],
        "current_step": task_info["current_step"],
        "created_at": task_info["created_at"],
        "updated_at": task_info["updated_at"],
        "error_message": task_info["error_message"]
    }


@router.get("/eval-tasks/{task_id}/result")
def get_task_result(task_id: str):
    """14.11 GET /runner/eval-tasks/{task_id}/result 返回结构化评测结果"""
    result = RunnerService.get_task_result(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return result

@router.get("/eval-tasks/{task_id}/logs")
def get_task_logs(task_id: str):
    """14.10 GET /runner/eval-tasks/{task_id}/logs 查看执行日志"""
    logs = RunnerService.get_task_logs(task_id)
    if not logs:
        raise HTTPException(status_code=404, detail="Task not found")
    return logs

@router.get("/eval-tasks/{task_id}/report")
def get_task_report(task_id: str):
    """14.12 GET /runner/eval-tasks/{task_id}/report 返回本地化报告"""
    report = RunnerService.get_task_report(task_id)
    if not report:
        raise HTTPException(status_code=404, detail="Task not found")
    return report

@router.get("/eval-tasks/{task_id}/bad-cases", response_model=BadCasesResponse)
def get_task_bad_cases(
    task_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    subset: Optional[str] = Query(None, description="Filter by subset name, e.g., ARC-Challenge")
):
    """分页获取任务错题集，供 Agent 分析"""
    bad_cases = RunnerService.get_task_bad_cases(task_id, limit, offset, subset)
    if not bad_cases:
        raise HTTPException(status_code=404, detail="Task not found")
    return bad_cases

@router.get("/eval-tasks/{task_id}/bad-cases", response_model=BadCasesResponse)
def get_task_bad_cases(
    task_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    subset: Optional[str] = Query(None, description="Filter by subset name, e.g., ARC-Challenge")
):
    """分页获取任务错题集，供 Agent 分析"""
    bad_cases = RunnerService.get_task_bad_cases(task_id, limit, offset, subset)
    if not bad_cases:
        raise HTTPException(status_code=404, detail="Task not found")
    return bad_cases
