@echo off
echo 语音识别后端服务启动脚本 (Windows版)

REM 创建必要的目录
if not exist temp_audio mkdir temp_audio
if not exist diyvoice\llmanswer mkdir diyvoice\llmanswer

REM 启动语音识别后端服务
echo 启动语音识别后端服务...
start /b pythonw shell_service.py > shell_service.log 2>&1

REM 输出提示信息
echo 服务已在后台启动，日志输出到 shell_service.log
echo 使用 'tasklist | findstr python' 查看进程
echo 使用 'taskkill /F /IM python.exe' 停止服务

pause