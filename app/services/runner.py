import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.schemas.runner import EvalTaskRequest, TaskStatus

# MVP 阶段使用内存存储任务状态，实际生产应替换为 Redis 或 Database
TASKS: Dict[str, Dict[str, Any]] = {
    # 预置一个专门用于测试分页错题的 Mock 任务
    "mock-task-12345": {
        "task_id": "mock-task-12345",
        "status": "SUCCESS",
        "model_service_id": "mock-model",
        "dataset": "arc",
        "work_dir": "result/mock-task-12345",
        "created_at": "2026-06-13T00:00:00Z",
        "updated_at": "2026-06-13T00:01:00Z",
        "current_step": "COMPLETED",
        "error_message": None,
        "config": {}
    }
}


class RunnerService:
    @staticmethod
    def validate_config(config: EvalTaskRequest) -> Dict[str, Any]:
        """
        仅校验配置，不真正执行。
        MVP 阶段仅做简单 Schema 校验（由 Pydantic 自动完成），这里返回标准化配置。
        """
        return {
            "valid": True,
            "normalized_config": config.model_dump(by_alias=True),
            "warnings": []
        }

    @staticmethod
    async def _execute_task_async(task_id: str, config: EvalTaskRequest):
        """
        后台异步执行 EvalScope 任务。
        """
        task = TASKS.get(task_id)
        if not task:
            return

        task["status"] = TaskStatus.RUNNING
        task["current_step"] = "EVALUATING"
        task["updated_at"] = datetime.now(timezone.utc).isoformat()

        try:
            work_dir = Path(config.output.work_dir)
            work_dir.mkdir(parents=True, exist_ok=True)
            
            # 构建 evalscope 真实执行命令
            # 兼容虚拟环境和系统全局环境的执行路径
            evalscope_bin = "evalscope"
            if Path("./venv/bin/evalscope").exists():
                evalscope_bin = "./venv/bin/evalscope"
                
            cmd = [
                evalscope_bin, "eval",
                "--model", config.model.model_name,
                "--api-url", config.model.api_url,
                "--api-key", config.model.api_key,
                "--eval-type", config.model.eval_type,
                "--datasets", config.dataset.name,
                "--limit", str(config.evaluation.limit),
                "--work-dir", str(work_dir)
            ]
            
            if config.evaluation.generation_config:
                gen_cfg_str = json.dumps(config.evaluation.generation_config.model_dump())
                cmd.extend(["--generation-config", gen_cfg_str])

            # 设置环境变量以防 evalscope 底层依赖 OPENAI_API_* 
            env = os.environ.copy()
            env["OPENAI_API_KEY"] = config.model.api_key
            env["OPENAI_API_BASE"] = config.model.api_url
            
            # 强制修改 ModelScope 的缓存目录到项目下，避免跨目录权限(PermissionError)问题
            local_cache_dir = Path.cwd() / ".cache"
            local_cache_dir.mkdir(parents=True, exist_ok=True)
            env["MS_CACHE_HOME"] = str(local_cache_dir)
            env["MODELSCOPE_CACHE"] = str(local_cache_dir / "modelscope")
            env["MODELSCOPE_MODULES_CACHE"] = str(local_cache_dir / "modelscope_modules")
            # 某些底层库还会尝试写入 ~/.modelscope，因此直接临时劫持 HOME 到缓存目录下
            env["HOME"] = str(local_cache_dir)
            
            # 异步调用子进程
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,  # 将 stderr 合并到 stdout
                env=env
            )
            
            # 实时读取并写入日志
            log_path = work_dir / "execution.log"
            with open(log_path, "wb") as f:
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    f.write(line)
                    f.flush()
            
            await process.wait()
            
            if process.returncode != 0:
                raise RuntimeError("EvalScope Execution Failed. Check execution.log for details.")

            task["status"] = TaskStatus.SUCCESS
            task["current_step"] = "COMPLETED"
            
            # 解析可能的输出
            task["metrics"] = {"note": "Actual evalscope execution completed. Please check report files in work_dir for detailed metrics."}
            task["report_path"] = str(work_dir)
            task["raw_result_path"] = str(work_dir)
            task["prediction_path"] = str(work_dir)
            
        except Exception as e:
            task["status"] = TaskStatus.FAILED
            task["error_message"] = str(e)
        finally:
            task["updated_at"] = datetime.now(timezone.utc).isoformat()

    @staticmethod
    def create_task(config: EvalTaskRequest, background_tasks) -> str:
        """
        创建并启动 EvalScope 评测任务
        """
        task_id = f"eval-task-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        
        TASKS[task_id] = {
            "task_id": task_id,
            "status": TaskStatus.QUEUED,
            "model_service_id": config.model.model_service_id,
            "dataset": config.dataset.name,
            "work_dir": config.output.work_dir,
            "created_at": now,
            "updated_at": now,
            "current_step": "QUEUED",
            "error_message": None,
            "config": config.model_dump(by_alias=True)
        }
        
        # 将实际执行抛入后台任务
        background_tasks.add_task(RunnerService._execute_task_async, task_id, config)
        return task_id

    @staticmethod
    def get_task(task_id: str) -> Optional[Dict[str, Any]]:
        """
        查询任务基本状态
        """
        return TASKS.get(task_id)

    @staticmethod
    def get_task_result(task_id: str) -> Optional[Dict[str, Any]]:
        """
        返回结构化评测结果
        """
        task = TASKS.get(task_id)
        if not task:
            return None
            
        return {
            "task_id": task["task_id"],
            "status": task["status"],
            "model_service_id": task["model_service_id"],
            "dataset": task["dataset"],
            "metrics": task.get("metrics", {}),
            "failed_cases": [],
            "paths": {
                "raw_result_path": task.get("raw_result_path", f"{task['work_dir']}/reports/raw.json"),
                "prediction_path": task.get("prediction_path", f"{task['work_dir']}/predictions/pred.jsonl"),
            }
        }

    @staticmethod
    def get_task_logs(task_id: str, tail_lines: int = 1000) -> Optional[Dict[str, Any]]:
        """
        获取执行日志
        """
        task = TASKS.get(task_id)
        if not task:
            return None
            
        work_dir = Path(task.get("work_dir", ""))
        log_path = work_dir / "execution.log"
        lines = []
        
        if log_path.exists():
            try:
                # 简单读取末尾若干行
                with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                    all_lines = f.readlines()
                    lines = all_lines[-tail_lines:]
            except Exception:
                lines = ["Error reading log file."]
        else:
            lines = ["Log file not created yet..."]
            
        return {
            "task_id": task_id,
            "log_path": str(log_path),
            "tail": [line.strip() for line in lines]
        }

    @staticmethod
    def get_task_bad_cases(task_id: str, limit: int = 20, offset: int = 0, subset_filter: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        分页获取任务的错题集 (从 reviews/*.jsonl 解析)
        """
        task = TASKS.get(task_id)
        if not task:
            return None
            
        work_dir = Path(task.get("work_dir", ""))
        all_bad_cases = []
        warnings = []
        
        # 查找最新的 timestamp 文件夹
        if work_dir.exists():
            subdirs = [d for d in work_dir.iterdir() if d.is_dir() and d.name.isdigit() or d.name.startswith("202")]
            if subdirs:
                latest_dir = sorted(subdirs)[-1]
                reviews_dir = latest_dir / "reviews"
                
                if reviews_dir.exists():
                    # 遍历所有 jsonl 文件
                    for jsonl_file in reviews_dir.glob("*/*.jsonl"):
                        # 文件名通常包含 subset 信息，例如 arc_ARC-Challenge.jsonl
                        filename = jsonl_file.stem
                        subset_name = filename.split("_")[-1] if "_" in filename else filename
                        
                        # 如果指定了过滤条件，跳过不匹配的文件
                        if subset_filter and subset_name != subset_filter:
                            continue
                            
                        try:
                            with open(jsonl_file, "r", encoding="utf-8") as f:
                                for line in f:
                                    if not line.strip():
                                        continue
                                    record = json.loads(line)
                                    
                                    # 解析对错：根据 sample_score 中的 acc 或者判断 extracted_prediction != target
                                    sample_score = record.get("sample_score", {})
                                    score_block = sample_score.get("score", {}) if isinstance(sample_score.get("score"), dict) else {}
                                    scores_dict = score_block.get("value", {})
                                    
                                    is_correct = False
                                    if "acc" in scores_dict:
                                        is_correct = float(scores_dict["acc"]) > 0.0
                                    else:
                                        target = str(record.get("target", ""))
                                        extracted = str(score_block.get("extracted_prediction", ""))
                                        is_correct = (target == extracted)
                                        
                                    if not is_correct:
                                        # 提取所需的字段
                                        messages = record.get("messages", [])
                                        prompt_text = ""
                                        assistant_perf = {}
                                        
                                        for msg in messages:
                                            if msg.get("role") == "user":
                                                prompt_text = msg.get("content", "")
                                            elif msg.get("role") == "assistant":
                                                assistant_perf = msg.get("perf_metrics") or {}
                                                
                                        # 为了防止 payload 过大，判断是否需要截断（简单逻辑：超过一定长度就截断，但为了 Agent 分析通常不截断）
                                        is_prompt_truncated = False
                                        is_pred_truncated = False
                                        
                                        case_item = {
                                            "case_id": f"{task_id}-{subset_name}-{record.get('index', 0)}",
                                            "index": record.get("index", 0),
                                            "subset": subset_name,
                                            "prompt": prompt_text,
                                            "target": str(record.get("target", "")),
                                            "prediction": str(score_block.get("prediction", "")),
                                            "extracted_prediction": str(score_block.get("extracted_prediction", "")),
                                            "correct": is_correct,
                                            "scores": scores_dict,
                                            "perf_metrics": assistant_perf,
                                            "sample_metadata": sample_score.get("sample_metadata", {}),
                                            "truncated": {
                                                "prompt": is_prompt_truncated,
                                                "prediction": is_pred_truncated
                                            }
                                        }
                                        all_bad_cases.append(case_item)
                        except Exception as e:
                            warnings.append(f"Failed to parse {jsonl_file.name}: {str(e)}")
                            
        # 分页逻辑
        # 按 index 或者 subset 简单排序一下保证一致性
        all_bad_cases.sort(key=lambda x: (x["subset"], x["index"]))
        
        total = len(all_bad_cases)
        sliced_items = all_bad_cases[offset : offset + limit]
        returned = len(sliced_items)
        has_more = (offset + limit) < total
        
        return {
            "task_id": task["task_id"],
            "status": task["status"],
            "model_service_id": task["model_service_id"],
            "dataset": task["dataset"],
            "source": "evalscope_reviews",
            "filters": {
                "subset": subset_filter
            } if subset_filter else {},
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": total,
                "returned": returned,
                "has_more": has_more,
                "next_offset": offset + limit if has_more else None
            },
            "items": sliced_items,
            "warnings": warnings
        }

    @staticmethod
    def get_task_report(task_id: str) -> Optional[Dict[str, Any]]:
        """
        返回本地化报告
        """
        task = TASKS.get(task_id)
        if not task:
            return None
            
        return {
            "task_id": task["task_id"],
            "report_format": task.get("config", {}).get("output", {}).get("report_format", "markdown"),
            "report_path": task.get("report_path", f"{task['work_dir']}/report.md"),
            "summary": "Mock summary based on local execution.",
            "download_url": f"/runner/eval-tasks/{task_id}/report/file"
        }
