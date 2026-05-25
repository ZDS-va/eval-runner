## 14. EvalScope Runner API 设计

### 14.1 Runner 的定位

EvalScope Runner 是底层评测执行服务。

它不负责理解自然语言，也不负责 Agent 规划。它只负责接收已经校验过的结构化评测配置，调用 EvalScope 执行评测任务，记录任务状态，解析输出目录，并将结果和报告路径返回给上层 Agent Orchestrator。

一句话：

> Agent Planner 负责“想清楚测什么”，EvalScope Runner 负责“安全、可追踪地把评测跑起来”。

---

### 14.2 Runner 的核心职责

1. 接收结构化 EvalScope 配置。
2. 校验模型 API、数据集、指标、输出路径和运行参数。
3. 将配置转换为 EvalScope CLI 参数或 Python TaskConfig。
4. 异步启动评测任务。
5. 记录任务状态、日志路径、输出路径和错误信息。
6. 查询任务进度。
7. 解析 EvalScope 输出目录。
8. 返回结构化评测结果。
9. 归档本地化报告。
10. 支持失败任务重试或基于缓存恢复。

---

### 14.3 Runner API 总览

推荐 API：

```text
GET  /runner/health
GET  /runner/capabilities
POST /runner/eval-tasks/validate
POST /runner/eval-tasks
GET  /runner/eval-tasks/{task_id}
GET  /runner/eval-tasks/{task_id}/progress
GET  /runner/eval-tasks/{task_id}/logs
GET  /runner/eval-tasks/{task_id}/result
GET  /runner/eval-tasks/{task_id}/report
POST /runner/eval-tasks/{task_id}/cancel
POST /runner/eval-tasks/{task_id}/retry
POST /runner/eval-tasks/{task_id}/parse
```

最小 MVP 可以先实现：

```text
GET  /runner/health
POST /runner/eval-tasks/validate
POST /runner/eval-tasks
GET  /runner/eval-tasks/{task_id}
GET  /runner/eval-tasks/{task_id}/result
GET  /runner/eval-tasks/{task_id}/report
```

---

### 14.4 GET /runner/health

用途：健康检查。

响应：

```json
{
  "status": "UP",
  "evalscope_available": true,
  "version": "1.2.0",
  "work_dir": "/mnt/eval-results",
  "timestamp": "2026-05-24T10:00:00Z"
}
```

说明：

1. 检查 EvalScope 是否可执行。
2. 检查输出目录是否可写。
3. 检查 Python 环境和依赖是否正常。

---

### 14.5 GET /runner/capabilities

用途：告诉上层 Agent 当前 Runner 支持什么。

响应：

```json
{
  "supported_eval_types": ["openai_api"],
  "supported_datasets": [
    {
      "name": "enterprise_qa_zh_v1",
      "scenario": "enterprise_qa",
      "language": "zh-CN",
      "path": "/mnt/datasets/enterprise_qa_zh_v1.jsonl"
    },
    {
      "name": "general_qa_zh_v1",
      "scenario": "general_qa",
      "language": "zh-CN",
      "path": "/mnt/datasets/general_qa_zh_v1.jsonl"
    }
  ],
  "supported_metrics": ["accuracy", "latency", "throughput", "failure_rate"],
  "max_concurrency": 10,
  "max_timeout_seconds": 300,
  "report_formats": ["json", "markdown", "html"]
}
```

说明：

这个接口非常适合 Agent 使用。Agent 规划前先调用 capabilities，避免生成系统不支持的数据集和指标。

---

### 14.6 POST /runner/eval-tasks/validate

用途：只校验配置，不真正执行。

请求：

```json
{
  "model": {
    "model_service_id": "model-service-001",
    "model_name": "qwen-7b",
    "api_url": "http://modelhub-gateway/v1",
    "api_key": "EMPTY",
    "eval_type": "openai_api"
  },
  "dataset": {
    "name": "enterprise_qa_zh_v1",
    "path": "/mnt/datasets/enterprise_qa_zh_v1.jsonl"
  },
  "evaluation": {
    "metrics": ["accuracy", "latency", "failure_rate"],
    "limit": 20,
    "concurrency": 1,
    "timeout_seconds": 60,
    "generation_config": {
      "temperature": 0.0,
      "max_tokens": 1024,
      "stream": true
    }
  },
  "output": {
    "work_dir": "/mnt/eval-results/task-001",
    "report_format": "markdown"
  }
}
```

响应：

```json
{
  "valid": true,
  "normalized_config": {
    "model": {
      "model_service_id": "model-service-001",
      "model_name": "qwen-7b",
      "api_url": "http://modelhub-gateway/v1",
      "api_key": "EMPTY",
      "eval_type": "openai_api"
    },
    "dataset": {
      "name": "enterprise_qa_zh_v1",
      "path": "/mnt/datasets/enterprise_qa_zh_v1.jsonl"
    },
    "evaluation": {
      "metrics": ["accuracy", "latency", "failure_rate"],
      "limit": 20,
      "concurrency": 1,
      "timeout_seconds": 60,
      "generation_config": {
        "temperature": 0.0,
        "max_tokens": 1024,
        "stream": true
      }
    },
    "output": {
      "work_dir": "/mnt/eval-results/task-001",
      "report_format": "markdown"
    }
  },
  "warnings": []
}
```

失败响应：

```json
{
  "valid": false,
  "errors": [
    {
      "field": "dataset.name",
      "message": "Unsupported dataset: unknown_dataset"
    },
    {
      "field": "evaluation.concurrency",
      "message": "concurrency must be between 1 and 10"
    }
  ]
}
```

---

### 14.7 POST /runner/eval-tasks

用途：创建并启动 EvalScope 评测任务。

请求结构与 validate 接口一致，可以额外增加执行选项：

```json
{
  "request_id": "req-20260524-001",
  "model": {
    "model_service_id": "model-service-001",
    "model_name": "qwen-7b",
    "api_url": "http://modelhub-gateway/v1",
    "api_key": "EMPTY",
    "eval_type": "openai_api"
  },
  "dataset": {
    "name": "enterprise_qa_zh_v1",
    "path": "/mnt/datasets/enterprise_qa_zh_v1.jsonl"
  },
  "evaluation": {
    "metrics": ["accuracy", "latency", "failure_rate"],
    "limit": 20,
    "concurrency": 1,
    "timeout_seconds": 60,
    "generation_config": {
      "temperature": 0.0,
      "max_tokens": 1024,
      "stream": true
    }
  },
  "output": {
    "work_dir": "/mnt/eval-results/task-001",
    "report_format": "markdown"
  },
  "execution": {
    "async": true,
    "enable_progress_tracker": true,
    "collect_perf": true,
    "use_cache": false,
    "ignore_errors": false
  }
}
```

响应：

```json
{
  "task_id": "eval-task-001",
  "status": "QUEUED",
  "work_dir": "/mnt/eval-results/task-001",
  "created_at": "2026-05-24T10:00:00Z"
}
```

内部执行可以转换为类似命令：

```bash
evalscope eval \
  --model qwen-7b \
  --api-url http://modelhub-gateway/v1 \
  --api-key EMPTY \
  --eval-type openai_api \
  --datasets enterprise_qa_zh_v1 \
  --limit 20 \
  --generation-config '{"temperature":0.0,"max_tokens":1024,"stream":true}' \
  --work-dir /mnt/eval-results/task-001 \
  --enable-progress-tracker \
  --collect-perf
```

或者用 Python TaskConfig/run_task 执行。

---

### 14.8 GET /runner/eval-tasks/{task_id}

用途：查询任务基本状态。

响应：

```json
{
  "task_id": "eval-task-001",
  "status": "RUNNING",
  "model_service_id": "model-service-001",
  "dataset": "enterprise_qa_zh_v1",
  "work_dir": "/mnt/eval-results/task-001",
  "current_step": "EVALUATING",
  "created_at": "2026-05-24T10:00:00Z",
  "updated_at": "2026-05-24T10:03:20Z",
  "error_message": null
}
```

状态建议：

```text
QUEUED
VALIDATING
RUNNING
PARSING_RESULT
GENERATING_REPORT
SUCCESS
FAILED
CANCELED
```

---

### 14.9 GET /runner/eval-tasks/{task_id}/progress

用途：读取 EvalScope progress.json 或 Runner 自己记录的进度。

响应：

```json
{
  "task_id": "eval-task-001",
  "status": "RUNNING",
  "processed_count": 52,
  "total_count": 100,
  "percent": 52.0,
  "stage": "Predicting",
  "updated_at": "2026-05-24T10:03:20Z"
}
```

说明：

如果 EvalScope 开启 progress tracker，可以优先读取 progress.json；如果没有，则使用 Runner 自己的任务状态。

---

### 14.10 GET /runner/eval-tasks/{task_id}/logs

用途：查看执行日志。

响应：

```json
{
  "task_id": "eval-task-001",
  "log_path": "/mnt/eval-results/task-001/logs/eval_log.log",
  "tail": [
    "Starting EvalScope task...",
    "Dataset enterprise_qa_zh_v1 loaded.",
    "Processed 52/100 samples."
  ]
}
```

---

### 14.11 GET /runner/eval-tasks/{task_id}/result

用途：返回结构化评测结果。

响应：

```json
{
  "task_id": "eval-task-001",
  "status": "SUCCESS",
  "model_service_id": "model-service-001",
  "dataset": "enterprise_qa_zh_v1",
  "metrics": {
    "accuracy": 0.78,
    "avg_latency_ms": 1320,
    "throughput_tokens_per_sec": 210.5,
    "failure_rate": 0.02
  },
  "failed_cases": [
    {
      "case_id": "case-001",
      "input": "什么是安全生产责任制？",
      "expected": "安全生产责任制是...",
      "actual": "安全生产是...",
      "reason": "答案缺少责任主体和制度要求。"
    }
  ],
  "paths": {
    "raw_result_path": "/mnt/eval-results/task-001/reports/qwen-7b/enterprise_qa_zh_v1.json",
    "prediction_path": "/mnt/eval-results/task-001/predictions/qwen-7b/enterprise_qa_zh_v1.jsonl",
    "review_path": "/mnt/eval-results/task-001/reviews/qwen-7b/enterprise_qa_zh_v1.jsonl"
  }
}
```

---

### 14.12 GET /runner/eval-tasks/{task_id}/report

用途：返回本地化报告。

响应：

```json
{
  "task_id": "eval-task-001",
  "report_format": "markdown",
  "report_path": "/mnt/eval-results/task-001/report.md",
  "summary": "该模型在企业知识库问答场景下准确率较高，但平均响应耗时偏高，建议进一步进行并发压测和长文本场景评测。",
  "download_url": "/runner/eval-tasks/eval-task-001/report/file"
}
```

---

### 14.13 POST /runner/eval-tasks/{task_id}/cancel

用途：取消任务。

响应：

```json
{
  "task_id": "eval-task-001",
  "status": "CANCELED",
  "message": "Evaluation task canceled."
}
```

实现要点：

1. 如果通过 subprocess 启动 EvalScope，需要保存 process id。
2. 取消时终止子进程。
3. 更新任务状态。
4. 保留已生成的日志和部分结果。

---

### 14.14 POST /runner/eval-tasks/{task_id}/retry

用途：重试失败任务。

请求：

```json
{
  "use_cache": true,
  "rerun_review": false
}
```

响应：

```json
{
  "old_task_id": "eval-task-001",
  "new_task_id": "eval-task-002",
  "status": "QUEUED",
  "message": "Retry task created."
}
```

说明：

如果 EvalScope 输出目录中已经有缓存，可以通过 use_cache 复用已有预测或评测结果。

---

### 14.15 POST /runner/eval-tasks/{task_id}/parse

用途：重新解析已有 EvalScope 输出目录，不重新执行评测。

请求：

```json
{
  "work_dir": "/mnt/eval-results/task-001",
  "regenerate_report": true
}
```

响应：

```json
{
  "task_id": "eval-task-001",
  "status": "SUCCESS",
  "result_parsed": true,
  "report_path": "/mnt/eval-results/task-001/report.md"
}
```