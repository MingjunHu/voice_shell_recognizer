#!/bin/bash

# 创建必要的目录
mkdir -p temp_audio
mkdir -p diyvoice/llmanswer

# 启动语音识别后端服务
echo "启动语音识别后端服务..."
nohup python shell_service.py > shell_service.log 2>&1 &

# 输出进程ID
echo "服务已在后台启动，日志输出到 shell_service.log"
echo "使用 'ps aux | grep shell_service.py' 查看进程"
echo "使用 'kill <PID>' 停止服务"