# 语音识别后端服务

这是一个基于Python的语音识别后端服务，可以监听设备麦克风输入，识别语音内容，调用大语言模型获取响应，并通过设备播放器播放响应音频。支持连续对话，实现真正的语音助手体验。

## 功能特点

- 实时监听设备麦克风
- 自动检测声音并开始录音
- 静音检测和最大录音时间限制
- 使用 faster-whisper 进行语音识别
- 调用阿里云百炼API获取LLM响应和语音合成
- 通过设备播放器播放响应音频
- 支持连续对话，无需手动重启

## 安装依赖

1. 安装系统依赖（根据操作系统不同）:

   **Ubuntu/Debian:**
   ```bash
   sudo apt-get install python3-pyaudio portaudio19-dev
   ```

   **CentOS:**
   ```bash
   sudo yum install -y portaudio portaudio-devel
   ```

   **macOS:**
   ```bash
   brew install portaudio
   ```

   **Windows:**
   ```
   无需额外系统依赖
   ```

2. 安装Python依赖:

   ```bash
   pip install -r requirements.txt
   ```

## 配置

1. 设置阿里云百炼API密钥（可选，如果已在代码中设置则不需要）:

   ```bash
   export DASHSCOPE_API_KEY="你的API密钥"
   ```

## 使用方法

1. 启动后端服务:

   **Linux/macOS:**
   ```bash
   ./shell_start.sh
   ```

   **Windows:**
   ```
   shell_start.bat
   ```

   或者直接运行:

   ```bash
   python shell_service.py
   ```

2. 服务将开始监听麦克风输入，当检测到声音时会自动开始录音。

3. 录音结束后（静音超过2秒或达到最大录音时间），服务会自动识别语音内容，调用LLM获取响应，并播放响应音频。

4. 按 `Ctrl+C` 停止服务。

## 日志

服务日志保存在 `shell_service.log` 文件中，可以通过以下命令查看:

```bash
tail -f shell_service.log
```

## 注意事项

- 确保麦克风设备正常工作并已正确配置
- 需要稳定的网络连接以访问阿里云百炼API
- 首次运行时会下载 faster-whisper 模型，可能需要一些时间

## 原理说明

1. **音频录制**：使用PyAudio库监听麦克风输入，检测到声音时开始录音，静音超过阈值或达到最大录音时间时停止录音。

2. **语音识别**：使用faster-whisper模型将录制的音频转换为文本。

3. **LLM响应**：将识别的文本发送到阿里云百炼API，获取文本响应和音频响应。

4. **音频播放**：使用PyAudio播放LLM返回的音频响应。

## 故障排除

- 如果遇到麦克风权限问题，请确保应用有访问麦克风的权限
- 如果语音识别结果不准确，可以尝试调整 `SILENCE_THRESHOLD` 和 `SILENCE_DURATION` 参数
- 如果播放音频时出现问题，请检查系统音频设置