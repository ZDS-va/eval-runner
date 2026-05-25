from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    QUEUED = "QUEUED"
    VALIDATING = "VALIDATING"
    RUNNING = "RUNNING"
    PARSING_RESULT = "PARSING_RESULT"
    GENERATING_REPORT = "GENERATING_REPORT"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


class ModelConfig(BaseModel):
    model_service_id: str
    model_name: str
    api_url: str
    api_key: str = "EMPTY"
    eval_type: str = "openai_api"


class DatasetConfig(BaseModel):
    name: str
    path: Optional[str] = None


class GenerationConfig(BaseModel):
    temperature: float = 0.0
    max_tokens: int = 1024
    stream: bool = True


class EvaluationConfig(BaseModel):
    metrics: List[str]
    limit: int = 20
    concurrency: int = 1
    timeout_seconds: int = 60
    generation_config: Optional[GenerationConfig] = None


class OutputConfig(BaseModel):
    work_dir: str
    report_format: str = "markdown"


class ExecutionConfig(BaseModel):
    is_async: bool = Field(True, alias="async")
    enable_progress_tracker: bool = True
    collect_perf: bool = True
    use_cache: bool = False
    ignore_errors: bool = False


class EvalTaskRequest(BaseModel):
    request_id: Optional[str] = None
    model: ModelConfig
    dataset: DatasetConfig
    evaluation: EvaluationConfig
    output: OutputConfig
    execution: Optional[ExecutionConfig] = None


class ValidateResponse(BaseModel):
    valid: bool
    normalized_config: Optional[EvalTaskRequest] = None
    warnings: List[str] = []
    errors: List[dict] = []


class CreateTaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    work_dir: str
    created_at: str
