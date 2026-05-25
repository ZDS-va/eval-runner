# 使用国内可访问的基础镜像源（例如南京大学或者阿里云公开镜像，这里以 dockerproxy/dockerpull 代理为例，或者直接使用原生并在系统层配置加速器）
# 如果下面的 docker.m.daocloud.io 失效，可替换回 python:3.12-slim 并确保宿主机配置了镜像加速
FROM docker.m.daocloud.io/library/python:3.12-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量，防止 python 缓存及输出缓冲
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 替换 apt 源为清华源以加速国内构建
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources || true

# 更新 apt 并安装必要的系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
# 使用清华大学的 pip 源进行加速安装
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 复制整个项目到镜像中
COPY . .

# 暴露后端 API 端口(8000) 和 前端 Streamlit 端口(8501)
EXPOSE 8000
EXPOSE 8501

# 给启动脚本增加可执行权限
RUN chmod +x /app/entrypoint.sh

# 启动脚本
CMD ["/app/entrypoint.sh"]
