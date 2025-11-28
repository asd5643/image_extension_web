# backend/main.py
import os
import shutil
import uuid
import requests
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles


from pathlib import Path

from core_logic import VideoExpander 

app = FastAPI()

# 初始化 GCS client
FILE_ID = "1dekKRF6rqbyUE1ODenr9RezTV3nJDoSk"   # <----- 記得改
BASE_URL = "https://drive.usercontent.google.com/download?id="  # 更穩定版 URL
DOWNLOAD_URL = f"{BASE_URL}{FILE_ID}&export=download"

# --- 設定 CORS (允許前端存取) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 開發階段允許所有來源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 設定路徑 ---
UPLOAD_DIR = "uploads"
RESULT_DIR = "results"
MODEL_NAME = "best_model.pt"
MODEL_PATH = Path("checkpoints") / MODEL_NAME # 請確認檔案存在

def download_from_google_drive(url, destination):
    print("Downloading model from Google Drive...")
    session = requests.Session()
    response = session.get(url, stream=True)

    # 如果是大檔案 → Google 會給 confirm token
    def get_confirm_token(resp):
        for k, v in resp.cookies.items():
            if k.startswith('download_warning'):
                return v
        return None

    token = get_confirm_token(response)
    if token:
        url_with_token = f"{url}&confirm={token}"
        response = session.get(url_with_token, stream=True)

    # 寫入檔案
    with open(destination, "wb") as f:
        for chunk in response.iter_content(8192):
            if chunk:
                f.write(chunk)

    print("Model downloaded successfully.")

# --- 啟動時檢查模型 ---
if not MODEL_PATH.exists():
    download_from_google_drive(DOWNLOAD_URL, MODEL_PATH)
else:
    print("Model already exists locally.")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)
os.makedirs("checkpoints", exist_ok=True) # 確保 checkpoints 資料夾存在

# 初始化模型 (全域變數，啟動時載入一次)
# device=None 會自動偵測: CUDA > MPS > CPU
expander = VideoExpander(model_path=MODEL_PATH, device=None) 

# --- 靜態檔案服務 ---
app.mount("/results", StaticFiles(directory=RESULT_DIR), name="results")
# original_uploads 這裡不需要 mount 了，因為 Resize 過的檔案也會放在 results 裡

# Root path for testing
@app.get("/")
def read_root():
    return {"message": "Video Expansion API is running! Access /docs for API details."}


def process_video_task(task_id: str, input_path: str, expanded_output_path: str, resized_original_output_path: str):
    """背景執行的任務函數，現在需要兩個輸出路徑"""
    print(f"[{task_id}] 開始處理影片...")
    try:
        # 呼叫你的核心邏輯，傳入兩個輸出路徑
        expander.process_video(input_path, expanded_output_path, resized_original_output_path)
        print(f"[{task_id}] 處理完成！")
        # 處理完後，可以刪除原始上傳的檔案
        if os.path.exists(input_path):
            os.remove(input_path)
            print(f"[{task_id}] 原始上傳影片已刪除: {input_path}")
    except Exception as e:
        print(f"[{task_id}] 處理失敗: {e}")

@app.post("/upload")
async def upload_video(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...)
):
    if not file.filename.lower().endswith((".mp4", ".mov", ".avi")):
        raise HTTPException(status_code=400, detail="只接受影片檔案 (mp4, mov, avi)")

    # 1. 產生唯一 ID
    task_id = str(uuid.uuid4())
    original_uploaded_filename = f"{task_id}_original_uploaded.mp4" # 原始上傳檔
    input_path = os.path.join(UPLOAD_DIR, original_uploaded_filename)
    
    # 擴大後的影片檔
    expanded_output_filename = f"{task_id}_expanded.mp4" 
    expanded_output_path = os.path.join(RESULT_DIR, expanded_output_filename)

    # Resize 過的原始影片檔 (用於前端比較)
    resized_original_output_filename = f"{task_id}_original_256x256.mp4"
    resized_original_output_path = os.path.join(RESULT_DIR, resized_original_output_filename)

    # 2. 儲存上傳的影片
    try:
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"儲存上傳檔案失敗: {e}")

    # 3. 加入背景任務
    background_tasks.add_task(
        process_video_task, 
        task_id, 
        input_path, 
        expanded_output_path, 
        resized_original_output_path
    )

    # 4. 回傳資訊給前端
    BASE_URL = "https://image-extension-web-backend.onrender.com"
    # 4. 回傳資訊給前端
    return {
        "task_id": task_id,
        "status": "processing",
        # 現在 original_video_url 指向的是 Resize 過的原始影片
        "original_video_url": f"{BASE_URL}/results/{resized_original_output_filename}",
        "processed_video_url": f"{BASE_URL}/results/{expanded_output_filename}"
    }

@app.get("/status/{task_id}")
def check_status(task_id: str):
    """加入 Debug Print 的版本"""
    
    expanded_filename = f"{task_id}_expanded.mp4"
    expanded_path = os.path.join(RESULT_DIR, expanded_filename)
    
    original_resized_filename = f"{task_id}_original_256x256.mp4"
    original_resized_path = os.path.join(RESULT_DIR, original_resized_filename)
    
    # Debug: 印出它在找什麼
    expanded_exists = os.path.exists(expanded_path)
    resized_exists = os.path.exists(original_resized_path)
    
    # 只有當找不到時才印 Log，避免 Log 洗版
    if not (expanded_exists and resized_exists):
        print(f"[DEBUG Status] Task: {task_id}")
        print(f"  - Looking for: {expanded_path} -> Exists? {expanded_exists}")
        print(f"  - Looking for: {original_resized_path} -> Exists? {resized_exists}")
        # 順便印出目前目錄下有什麼，方便除錯
        print(f"  - Current files in {RESULT_DIR}: {os.listdir(RESULT_DIR)}")

    if expanded_exists and resized_exists:
        return {"status": "completed"}
    else:
        return {"status": "processing"}
