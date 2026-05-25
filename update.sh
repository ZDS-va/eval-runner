#!/bin/bash

echo "🚀 开始更新 eval-runner 项目..."

# 1. 拉取最新代码
echo "📦 正在从 Git 拉取最新代码..."
git pull origin main

# 2. 重新构建并重启容器
# --build: 强制重新构建镜像
# -d: 后台运行
echo "🐳 正在重新构建并重启 Docker 容器..."
docker-compose up -d --build

# 3. 清理不再使用的旧镜像（可选，保持服务器磁盘整洁）
echo "🧹 清理悬空镜像..."
docker image prune -f

echo "✅ 更新部署完成！前端访问地址: http://<你的服务器IP>:8501"
