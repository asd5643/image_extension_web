#!/bin/bash

# ==========================================
#       AI Video Expand - Unified Launcher
# ==========================================

# 1. 偵測作業系統 (OS Detection)
OS="$(uname -s)"
case "${OS}" in
    CYGWIN*|MINGW*|MSYS*) IS_WIN=true ;;
    *) IS_WIN=false ;;
esac

echo "[Launcher] Detected OS: $OS"

# 定義關閉函數：按 Ctrl+C 時殺掉所有背景程序
cleanup() {
    echo ""
    echo "正在停止服務..."
    # 殺掉背景的 Python/Node 程序
    if [ "$IS_WIN" = true ]; then
        taskkill //F //IM uvicorn.exe //T > /dev/null 2>&1
        taskkill //F //IM node.exe //T > /dev/null 2>&1
    else
        kill $(jobs -p) 2>/dev/null
    fi
    exit
}
trap cleanup SIGINT

# 2. 檢查 FFmpeg
echo "Checking FFmpeg..."
if ! command -v ffmpeg &> /dev/null; then
    echo "[ERROR] 找不到 FFmpeg，請先安裝！"
    if [ "$IS_WIN" = true ]; then
        echo "   Windows: 請下載 FFmpeg 並設定環境變數 Path"
    else
        echo "   Mac: brew install ffmpeg"
    fi
    exit 1
fi

# 3. 準備後端
echo "[Backend] Starting FastAPI..."
cd backend

# 決定 Python 指令 (Windows 可能是 python, Mac 可能是 python3)
if command -v python3 &> /dev/null; then
    PY_CMD=python3
else
    PY_CMD=python
fi

# 建立虛擬環境
if [ ! -d ".venv" ]; then
    echo "   -> Creating virtual environment..."
    $PY_CMD -m venv .venv
fi

# 啟動虛擬環境 (自動判斷路徑)
if [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate  # Windows
elif [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate      # Mac/Linux
else
    echo "[ERROR] 無法找到虛擬環境啟動腳本"
    exit 1
fi

echo "   -> Installing dependencies..."
pip install -q -r requirements.txt

# 啟動後端 (在背景執行)
# 注意：Windows Git Bash 下 uvicorn 需要 winpty 嗎？通常不用，但直接執行較保險
python -m uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!
echo "Backend running (PID: $BACKEND_PID)"

# 4. 準備前端
echo "[Frontend] Starting React..."
cd ../frontend

if [ ! -d "node_modules" ]; then
    echo "   -> Installing npm packages..."
    npm install
fi

echo "Frontend running..."
npm run dev

# 等待結束
wait