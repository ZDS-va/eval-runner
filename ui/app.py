import time

import requests
import streamlit as st

API_URL = "http://127.0.0.1:8000/runner"

st.set_page_config(page_title="EvalScope Runner Dashboard", layout="wide")

st.title("🚀 EvalScope Runner Dashboard")

# 检查服务健康状态
st.sidebar.header("Service Status")
try:
    health_res = requests.get(f"{API_URL}/health", timeout=2)
    if health_res.status_code == 200:
        st.sidebar.success("Runner Service: UP")
    else:
        st.sidebar.error("Runner Service: DOWN")
except Exception:
    st.sidebar.error("Runner Service: UNREACHABLE")

# ================= 任务提交区 =================
st.header("1. Submit Evaluation Task")

st.subheader("Model Config")
col1, col2 = st.columns(2)
with col1:
    model_name = st.text_input("Model Name", value="qwen-7b")
    model_service_id = st.text_input("Service ID", value="model-service-001")
with col2:
    api_url = st.text_input("API URL", value="http://modelhub-gateway/v1")
    api_key = st.text_input("API Key", value="EMPTY", type="password")

if st.button("🔌 Test API Connection"):
    with st.spinner("Testing connection..."):
        try:
            # Normalizing the URL
            test_url = api_url.rstrip("/")
            if not test_url.endswith("/chat/completions"):
                test_url = f"{test_url}/chat/completions"
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": "Hello! Reply with exactly 'OK' if you receive this."}],
                "max_tokens": 10
            }
            resp = requests.post(test_url, headers=headers, json=payload, timeout=10)
            if resp.status_code == 200:
                content = resp.json().get('choices', [{}])[0].get('message', {}).get('content', '')
                st.success(f"Connection Successful! Model replied: {content}")
            else:
                st.error(f"Connection Failed! Status: {resp.status_code}\n\nResponse: {resp.text}")
        except Exception as e:
            st.error(f"Request Error: {str(e)}")

st.subheader("Dataset Config")
col3, col4 = st.columns(2)
with col3:
    dataset_name = st.text_input("Dataset Name", value="arc")
    limit = st.number_input("Limit (Samples to evaluate)", value=3, min_value=1, max_value=1000)
with col4:
    dataset_path = st.text_input("Dataset Path (Optional)", value="")

st.subheader("Evaluation Config")
metrics = st.multiselect("Metrics", ["accuracy", "latency", "throughput", "failure_rate"], default=["accuracy", "latency"])

if st.button("🚀 Submit Task", type="primary"):
    payload = {
        "model": {
            "model_service_id": model_service_id,
            "model_name": model_name,
            "api_url": api_url,
            "api_key": api_key,
            "eval_type": "openai_api"
        },
        "dataset": {
            "name": dataset_name,
            "path": dataset_path
        },
        "evaluation": {
            "metrics": metrics,
            "limit": limit,
            "concurrency": 1,
            "timeout_seconds": 60,
            "generation_config": {
                "temperature": 0.0,
                "max_tokens": 1024,
                "stream": False
            }
        },
        "output": {
            "work_dir": f"result/{model_name}-{int(time.time())}",
            "report_format": "markdown"
        },
        "execution": {
            "async": True,
            "enable_progress_tracker": True,
            "collect_perf": True,
            "use_cache": False,
            "ignore_errors": False
        }
    }
    
    try:
        res = requests.post(f"{API_URL}/eval-tasks", json=payload)
        if res.status_code == 200:
            data = res.json()
            st.session_state["task_id"] = data["task_id"]
            st.success(f"Task created successfully! Task ID: {data['task_id']}")
        else:
            st.error(f"Failed to create task: {res.text}")
    except Exception as e:
        st.error(f"Request failed: {e}")

st.divider()

# ================= 状态与结果查询区 =================
st.header("2. Track Task Status & Result")

task_id_input = st.text_input("Enter Task ID to track:", value=st.session_state.get("task_id", ""))

if task_id_input:
    col_status, col_result = st.columns(2)
    
    # 状态查询
    with col_status:
        if st.button("Refresh Status & Logs"):
            try:
                res = requests.get(f"{API_URL}/eval-tasks/{task_id_input}")
                if res.status_code == 200:
                    data = res.json()
                    st.write(f"**Status**: `{data['status']}`")
                    st.write(f"**Current Step**: {data['current_step']}")
                    st.write(f"**Updated At**: {data['updated_at']}")
                    if data['error_message']:
                        st.error(f"Error: {data['error_message']}")
                else:
                    st.error("Task not found or error occurred.")
            except Exception as e:
                st.error(f"Error fetching status: {e}")
                
    # 结果查询
    with col_result:
        if st.button("Get Result"):
            try:
                res = requests.get(f"{API_URL}/eval-tasks/{task_id_input}/result")
                if res.status_code == 200:
                    data = res.json()
                    if data["status"] == "SUCCESS":
                        st.success("Evaluation Completed!")
                        st.json(data["metrics"])
                        st.info(f"Result Path: {data['paths']['raw_result_path']}")
                    else:
                        st.warning(f"Task is not SUCCESS yet. Current status: {data['status']}")
                else:
                    st.error("Result not available or task not found.")
            except Exception as e:
                st.error(f"Error fetching result: {e}")

    # 终端日志显示区
    st.subheader("Terminal Logs")
    log_container = st.empty()
    
    try:
        log_res = requests.get(f"{API_URL}/eval-tasks/{task_id_input}/logs")
        if log_res.status_code == 200:
            log_data = log_res.json()
            lines = log_data.get("tail", [])
            log_text = "\n".join(lines)
            if not log_text.strip():
                log_text = "Waiting for logs to generate..."
            log_container.code(log_text, language="bash")
    except Exception as e:
        log_container.error(f"Failed to fetch logs: {e}")
