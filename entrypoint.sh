#!/bin/bash

# 启动 FastAPI 后端服务 (挂后台)
uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# 启动 Streamlit 前端服务 (挂前台阻塞)
streamlit run ui/app.py --server.port 8501 --server.address 0.0.0.0
