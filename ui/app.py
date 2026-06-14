import time

import requests
import streamlit as st
import streamlit.components.v1 as components

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

# 获取历史任务列表
history_tasks = []
try:
    res_tasks = requests.get(f"{API_URL}/eval-tasks", timeout=2)
    if res_tasks.status_code == 200:
        history_tasks = res_tasks.json().get("tasks", [])
except Exception:
    pass

task_options = ["-- Enter Manually --"] + [f"{t['task_id']} ({t['model_service_id']} - {t['status']})" for t in history_tasks]
selected_option = st.selectbox("Select a recent task to view:", task_options)

default_task_id = st.session_state.get("task_id", "")
if selected_option != "-- Enter Manually --":
    default_task_id = selected_option.split(" ")[0]

task_id_input = st.text_input("Enter Task ID to track:", value=default_task_id)
auto_refresh = st.checkbox("Auto-refresh terminal logs & status", value=True)

if task_id_input:
    status_container = st.empty()
    
    tab1, tab2, tab3 = st.tabs(["Terminal Logs", "Evaluation Result", "HTML Report Info"])
    
    with tab1:
        log_container = st.empty()
    with tab2:
        result_container = st.empty()
    with tab3:
        report_container = st.empty()

    def fetch_and_update_status():
        try:
            res = requests.get(f"{API_URL}/eval-tasks/{task_id_input}")
            if res.status_code == 200:
                data = res.json()
                status_text = f"**Status**: `{data['status']}` | **Current Step**: {data['current_step']} | **Updated At**: {data['updated_at']}"
                if data['error_message']:
                    status_container.error(f"{status_text}\n\n**Error**: {data['error_message']}")
                else:
                    status_container.info(status_text)
                return data['status']
            else:
                status_container.error("Task not found or error occurred.")
                return "ERROR"
        except Exception as e:
            status_container.error(f"Error fetching status: {e}")
            return "ERROR"

    def fetch_logs():
        try:
            log_res = requests.get(f"{API_URL}/eval-tasks/{task_id_input}/logs")
            if log_res.status_code == 200:
                log_data = log_res.json()
                lines = log_data.get("tail", [])
                if not lines or all(not l.strip() for l in lines):
                    lines = ["Waiting for logs to generate..."]
                
                # 将日志行反转，并各自包裹在一个 div 中。
                # 配合外层容器的 flex-direction: column-reverse，这样最新的日志就会紧贴在容器底部（自动置底）
                reversed_lines = lines[::-1]
                divs = "".join(f"<div>{line}</div>" for line in reversed_lines)
                
                # 使用 markdown 和 CSS 将原生的内容固定高度并支持滚动
                html_code = f"""
                <div style="
                    background-color: #1e1e1e;
                    color: #00ff00;
                    font-family: monospace;
                    height: 400px;
                    overflow-y: auto;
                    padding: 10px;
                    border-radius: 5px;
                    white-space: pre-wrap;
                    font-size: 14px;
                    display: flex;
                    flex-direction: column-reverse;
                ">
                    {divs}
                </div>
                """
                log_container.markdown(html_code, unsafe_allow_html=True)
        except Exception as e:
            log_container.error(f"Failed to fetch logs: {e}")
            
    def fetch_result():
        try:
            res = requests.get(f"{API_URL}/eval-tasks/{task_id_input}/result")
            if res.status_code == 200:
                data = res.json()
                if data["status"] == "SUCCESS":
                    with result_container.container():
                        st.success("Evaluation Completed!")
                        st.json(data["metrics"])
                        st.info(f"Result Path: {data['paths']['raw_result_path']}")
                else:
                    with result_container.container():
                        st.info("Evaluation is not completed yet.")
        except Exception as e:
            result_container.error(f"Failed to fetch result: {e}")

    def fetch_report():
        try:
            res = requests.get(f"{API_URL}/eval-tasks/{task_id_input}/report")
            if res.status_code == 200:
                data = res.json()
                with report_container.container():
                    st.write("**Report Path:**", data.get("report_path"))
                    st.json(data)
        except Exception:
            pass

    # 初次加载
    current_status = fetch_and_update_status()
    fetch_logs()
    
    if current_status == "SUCCESS":
        fetch_result()
        fetch_report()

    # 自动轮询机制 (如果开启且任务未结束)
    if auto_refresh and current_status in ["QUEUED", "RUNNING", "VALIDATING", "PARSING_RESULT"]:
        time.sleep(2)
        st.rerun()
