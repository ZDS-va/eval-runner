FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量，防止 python 缓存及输出缓冲
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 更新 apt 并安装必要的系统依赖（如果 evalscope 或其底层有额外依赖可以加在这里）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制整个项目到镜像中
COPY . .

# 暴露后端 API 端口(8000) 和 前端 Streamlit 端口(8501)
EXPOSE 8000
EXPOSE 8501

# 给启动脚本增加可执行权限
RUN chmod +x /app/entrypoint.sh

# 启动脚本
CMD ["/app/entrypoint.sh"]
