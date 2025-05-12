from fastapi import FastAPI, File, UploadFile, Request, Response
import os
from openai import OpenAI
import base64
import io
from pydub import AudioSegment
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from faster_whisper import WhisperModel
import shutil
import os
from datetime import datetime
import numpy as np
import soundfile as sf

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# 添加静态文件服务，使llmanswer目录可被访问
from fastapi.staticfiles import StaticFiles
app.mount("/diyvoice/llmanswer", StaticFiles(directory="diyvoice/llmanswer"), name="llmanswer")

# 加载 FastWhisper 模型（可选择 base、small、medium 等）
# model = WhisperModel("large-v3", device="cuda", compute_type="int8_float16")
model = WhisperModel("medium", device="cpu", compute_type="int8")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/diyvoice", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/diyvoice/upload-audio/")
async def upload_audio(file: UploadFile = File(...)):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{UPLOAD_DIR}/audio_{timestamp}.webm"
    
    with open(filename, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    print(f"收到音频：{filename}")
    try:
        segments, info = model.transcribe(filename, language='zh',beam_size=5)
        full_text = "".join(segment.text for segment in segments)
        print("识别结果：", full_text)
    finally:
        # 确保即使报错也会清理文件
        if os.path.exists(filename):
            os.remove(filename)
            print(f"已删除文件：{filename}")

    return {"text": full_text}

@app.post("/diyvoice/generate-tts/")
async def generate_tts(request: Request):
    data = await request.json()
    text = data.get("text")
    print(f"TTS请求文本: {text}")
    
    client = OpenAI(
        api_key="xMJKMQQmFiv4G4HyouBnXI764sq8BttpC8848E7DD8F911ED9A5512FBC092A79E",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    
    print("正在调用TTS API...")
    completion = client.chat.completions.create(
        model="qwen-omni-turbo",
        messages=[{"role": "user", "content": text}],
        modalities=["text","audio"],
        audio={"voice": "Cherry", "format": "wav"},
        stream=True,
        stream_options={"include_usage": True},
    )

    try:
        audio_string = ""
        for chunk in completion:
            if chunk.choices:
                if hasattr(chunk.choices[0].delta, "audio"):
                    try:
                        audio_string += chunk.choices[0].delta.audio["data"]
                    except Exception as e:
                        print(chunk.choices[0].delta.audio["transcript"])
            else:
                print(chunk.usage)

        wav_bytes = base64.b64decode(audio_string)
        audio_np = np.frombuffer(wav_bytes, dtype=np.int16)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"diyvoice/llmanswer/tts_{timestamp}.wav"
        with open(output_filename, "wb") as f:
            f.write(wav_bytes)
        print(f"Audio saved to {output_filename}")
        sf.write(output_filename, audio_np, samplerate=24000)
    
        return {"status": "success", "file_path": output_filename}
    except Exception as e:
        print(f"TTS generation error: {str(e)}")
        return Response(content="", status_code=500)

@app.post("/diyvoice/delete-audio/")
async def delete_audio(request: Request):
    data = await request.json()
    file_path = data.get("file_path")
    
    # 安全检查：确保只删除llmanswer目录下的文件
    if not file_path or not file_path.startswith("diyvoice/llmanswer/"):
        return {"status": "error", "message": "Invalid file path"}
    
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Deleted audio file: {file_path}")
            return {"status": "success"}
        return {"status": "error", "message": "File not found"}
    except Exception as e:
        print(f"Delete audio error: {str(e)}")
        return {"status": "error", "message": str(e)}