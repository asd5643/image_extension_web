# 使用官方 Python 3.9 輕量版映像檔
FROM python:3.9-slim

# 1. 安裝系統級依賴 (包含 FFmpeg 和 OpenCV 需要的函式庫)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# 2. 設定工作目錄
WORKDIR /app

# 3. 複製依賴清單並安裝 Python 套件
COPY requirements.txt .
# 加上 --no-cache-dir 可以減少映像檔大小
RUN pip install --no-cache-dir -r requirements.txt

# 4. 複製所有程式碼進去
COPY . .

# 5. 建立必要的資料夾 (避免執行時報錯)
RUN mkdir -p uploads results checkpoints

# 6. 開放 Port
EXPOSE 8000

# 7. 啟動指令 (Host 設為 0.0.0.0 才能讓外部存取)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]