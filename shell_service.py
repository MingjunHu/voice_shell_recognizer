#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
语音识别后端服务
监听设备麦克风，识别语音，调用LLM获取响应，并通过设备播放器播放
"""

import os
import time
import wave
import numpy as np
import pyaudio
import soundfile as sf
import base64
from datetime import datetime
from faster_whisper import WhisperModel
from openai import OpenAI
import logging

# 目录设置
TEMP_DIR = "temp_audio"
os.makedirs(TEMP_DIR, exist_ok=True)

# 配置日志
try:
    # 使用临时目录中的日志文件
    log_file = os.path.join(TEMP_DIR, "shell_service.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
except Exception as e:
    # 如果无法创建文件处理器，则只使用控制台输出
    print(f"无法配置日志文件: {str(e)}")
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )
logger = logging.getLogger("ShellService")

# 音频参数
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
SILENCE_THRESHOLD = 1000  # 静音阈值
SILENCE_DURATION = 2  # 静音持续时间（秒）
MAX_RECORD_DURATION = 20  # 最大录音时间（秒）

# 加载 Whisper 模型
logger.info("正在加载语音识别模型...")
model = WhisperModel("medium", device="cpu", compute_type="int8")
logger.info("语音识别模型加载完成")

# 阿里云百炼API客户端
client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

class AudioRecorder:
    """音频录制器"""
    
    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.frames = []
        self.is_recording = False
        self.silence_start_time = None
        self.record_start_time = None
        self.last_recording_time = 0  # 上次录音结束时间
    
    def start_stream(self):
        """开始音频流"""
        try:
            # 确保之前的流已关闭
            if self.stream:
                try:
                    self.stream.stop_stream()
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None
            
            # 创建新的音频流
            self.stream = self.p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK
            )
            logger.info("麦克风监听已启动")
        except Exception as e:
            logger.error(f"启动麦克风监听出错: {str(e)}")
            # 尝试重新初始化PyAudio
            try:
                self.p.terminate()
                time.sleep(0.5)
                self.p = pyaudio.PyAudio()
                self.stream = self.p.open(
                    format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK
                )
                logger.info("麦克风监听已重新启动")
            except Exception as e2:
                logger.error(f"重新启动麦克风监听失败: {str(e2)}")
    
    def start_recording(self):
        """开始录音"""
        # 确保距离上次录音结束有足够的间隔
        current_time = time.time()
        if current_time - self.last_recording_time < 1.0:  # 至少1秒的间隔
            logger.info(f"距离上次录音结束时间太短，等待...")
            time.sleep(1.0)
        
        self.frames = []
        self.is_recording = True
        self.record_start_time = time.time()
        self.silence_start_time = None
        logger.info("开始录音...")
    
    def stop_recording(self, reason=""):
        """停止录音"""
        self.is_recording = False
        self.last_recording_time = time.time()  # 记录录音结束时间
        logger.info(f"停止录音: {reason}")
        return self.save_audio()
    
    def save_audio(self):
        """保存录音为WAV文件"""
        if not self.frames:
            logger.warning("没有录制到音频数据")
            return None
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{TEMP_DIR}/recording_{timestamp}.wav"
            
            wf = wave.open(filename, 'wb')
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(self.p.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(self.frames))
            wf.close()
            
            logger.info(f"录音已保存: {filename}")
            return filename
        except Exception as e:
            logger.error(f"保存音频文件出错: {str(e)}")
            return None
    
    def process_audio(self):
        """处理音频流"""
        if not self.stream or not self.stream.is_active():
            self.start_stream()
            # 给麦克风一点时间准备
            time.sleep(0.1)
        
        try:
            # 检查流是否可读
            if not self.stream or not self.stream.is_active():
                logger.warning("音频流不可用，重新启动...")
                self.start_stream()
                return None
            
            try:
                data = self.stream.read(CHUNK, exception_on_overflow=False)
                audio_data = np.frombuffer(data, dtype=np.int16)
                volume = np.abs(audio_data).mean()
                
                # 检测是否有声音
                if volume > SILENCE_THRESHOLD:
                    if not self.is_recording:
                        # 确保距离上次录音有足够间隔
                        if time.time() - self.last_recording_time < 1.0:
                            return None
                        self.start_recording()
                        logger.info(f"检测到声音(音量: {volume:.2f})，开始录音...")
                    self.frames.append(data)
                    self.silence_start_time = None
                elif self.is_recording:
                    self.frames.append(data)
                    
                    # 检测静音
                    if self.silence_start_time is None:
                        self.silence_start_time = time.time()
                    elif time.time() - self.silence_start_time > SILENCE_DURATION:
                        return self.stop_recording("静音超过阈值")
                    
                    # 检测最大录音时间
                    if time.time() - self.record_start_time > MAX_RECORD_DURATION:
                        return self.stop_recording("达到最大录音时间")
                
                return None
            except Exception as e:
                logger.error(f"读取音频数据出错: {str(e)}")
                # 尝试重新启动流
                self.start_stream()
                return None
        except Exception as e:
            logger.error(f"处理音频时出错: {str(e)}")
            # 重置状态
            self.is_recording = False
            self.silence_start_time = None
            self.frames = []
            # 尝试重新启动流
            time.sleep(0.5)
            self.start_stream()
            return None
    
    def close(self):
        """关闭资源"""
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.p.terminate()
        logger.info("音频资源已释放")


class AudioPlayer:
    """音频播放器"""
    
    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.is_playing = False
    
    def play_audio(self, audio_data, sample_rate=24000):
        """播放音频数据"""
        if self.is_playing:
            logger.warning("已有音频正在播放，等待完成...")
            return
            
        self.is_playing = True
        try:
            # 确保之前的流已关闭
            if self.stream:
                try:
                    self.stream.stop_stream()
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None
            
            # 创建新的音频流
            self.stream = self.p.open(
                format=self.p.get_format_from_width(2),  # 16位音频
                channels=1,
                rate=sample_rate,
                output=True
            )
            
            logger.info("开始播放音频...")
            self.stream.write(audio_data.tobytes())
            logger.info("音频播放完成")
            
            # 关闭流
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        except Exception as e:
            logger.error(f"播放音频时出错: {str(e)}")
            if self.stream:
                try:
                    self.stream.stop_stream()
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None
        finally:
            self.is_playing = False
            logger.info("音频播放器已重置，准备下一次播放")
    
    def close(self):
        """关闭资源"""
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception as e:
                logger.error(f"关闭音频流时出错: {str(e)}")
        self.p.terminate()
        logger.info("音频播放器资源已释放")


def transcribe_audio(audio_file):
    """使用Whisper模型转录音频"""
    try:
        logger.info(f"正在识别音频: {audio_file}")
        segments, info = model.transcribe(audio_file, language='zh', beam_size=5)
        text = "".join(segment.text for segment in segments)
        logger.info(f"识别结果: {text}")
        return text
    except Exception as e:
        logger.error(f"音频识别出错: {str(e)}")
        return ""


def get_llm_response(text):
    """获取LLM响应"""
    if not text.strip():
        return None
    
    try:
        logger.info(f"发送文本到LLM: {text}")
        completion = client.chat.completions.create(
            model="qwen-omni-turbo",
            messages=[{"role": "user", "content": text}],
            modalities=["text", "audio"],
            audio={"voice": "Cherry", "format": "wav"},
            stream=True,
            stream_options={"include_usage": True},
        )
        
        audio_string = ""
        for chunk in completion:
            if chunk.choices and chunk.choices[0].delta:
                delta = chunk.choices[0].delta
                if hasattr(delta, "audio") and delta.audio:
                    try:
                        if "data" in delta.audio:
                            audio_string += delta.audio["data"]
                        elif "transcript" in delta.audio:
                            logger.info(f"音频转写: {delta.audio['transcript']}")
                    except Exception as e:
                        logger.error(f"处理音频数据出错: {str(e)}")
                elif hasattr(delta, "content") and delta.content:
                    logger.info(f"LLM文本响应: {delta.content}")
        
        if audio_string:
            try:
                wav_bytes = base64.b64decode(audio_string)
                audio_np = np.frombuffer(wav_bytes, dtype=np.int16)
                logger.info("LLM响应音频数据已接收")
                return audio_np
            except Exception as e:
                logger.error(f"解码音频数据出错: {str(e)}")
                return None
        else:
            logger.warning("未收到LLM音频响应")
            return None
    except Exception as e:
        logger.error(f"获取LLM响应出错: {str(e)}")
        return None


def cleanup_temp_files():
    """清理临时文件"""
    try:
        for file in os.listdir(TEMP_DIR):
            file_path = os.path.join(TEMP_DIR, file)
            if os.path.isfile(file_path):
                os.remove(file_path)
        logger.info("临时文件已清理")
    except Exception as e:
        logger.error(f"清理临时文件出错: {str(e)}")


def main():
    """主函数"""
    logger.info("启动语音识别后端服务")
    
    recorder = AudioRecorder()
    player = AudioPlayer()
    
    try:
        logger.info("按Ctrl+C退出程序")
        conversation_count = 0
        
        while True:
            try:
                # 处理音频并检查是否有录音完成
                audio_file = recorder.process_audio()
                
                if audio_file:
                    # 转录音频
                    text = transcribe_audio(audio_file)
                    
                    if text:
                        # 获取LLM响应
                        audio_data = get_llm_response(text)
                        
                        if audio_data is not None:
                            # 播放响应
                            player.play_audio(audio_data)
                            conversation_count += 1
                            logger.info(f"完成第 {conversation_count} 轮对话")
                    
                    # 删除临时音频文件
                    try:
                        os.remove(audio_file)
                        logger.info(f"已删除临时文件: {audio_file}")
                    except Exception as e:
                        logger.error(f"删除文件出错: {str(e)}")
                    
                    # 重置录音状态，准备下一轮对话
                    recorder.is_recording = False
                    recorder.silence_start_time = None
                    recorder.frames = []
                    logger.info("准备下一轮对话...")
                
                # 短暂休眠以减少CPU使用
                time.sleep(0.01)
            except Exception as e:
                logger.error(f"主循环处理出错: {str(e)}")
                # 重置录音状态，确保能继续监听
                recorder.is_recording = False
                recorder.silence_start_time = None
                recorder.frames = []
                logger.info("重置状态，继续监听...")
                time.sleep(1)  # 出错后稍微等待一下再继续
    
    except KeyboardInterrupt:
        logger.info("接收到退出信号")
    except Exception as e:
        logger.error(f"程序运行出错: {str(e)}")
    finally:
        # 清理资源
        recorder.close()
        player.close()
        cleanup_temp_files()
        logger.info("程序已退出")


if __name__ == "__main__":
    main()