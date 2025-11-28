// frontend/src/App.jsx
import { useState, useEffect, useRef } from 'react';
import './App.css';

function App() {
  const [file, setFile] = useState(null);
  const [taskId, setTaskId] = useState(null);
  const [status, setStatus] = useState('idle'); 
  const [videoUrls, setVideoUrls] = useState({ original: '', processed: '' });
  const [progress, setProgress] = useState(0); 
  const [error, setError] = useState(null);

  // Refs
  const vid1Ref = useRef(null);
  const vid2Ref = useRef(null);
  const isSyncing = useRef(false);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setStatus('idle');
      setProgress(0);
      setError(null);
      setVideoUrls({ original: '', processed: '' });
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setError("請先選擇一個影片檔案 📂");
      return;
    }
    
    setStatus('uploading');
    setError(null);
    const formData = new FormData();
    formData.append('file', file);

    try {
      // 注意：如果你已經部署到 Server，這裡的路徑要改成 Server IP
      // 如果是 Docker 本機跑，localhost 沒問題
      const response = await fetch('https://image-extension-web-backend.onrender.com', {
        method: 'POST',
        body: formData,
      });
      
      if (!response.ok) throw new Error("上傳失敗，請檢查後端服務");

      const data = await response.json();
      setTaskId(data.task_id);
      setVideoUrls({
        original: data.original_video_url,
        processed: data.processed_video_url
      });
      setStatus('processing');
      
    } catch (err) {
      console.error(err);
      setError(err.message);
      setStatus('idle');
    }
  };

  // Polling Status
  useEffect(() => {
    let intervalId;
    if (status === 'processing' && taskId) {
      intervalId = setInterval(async () => {
        try {
          const res = await fetch(`http://localhost:8000/status/${taskId}`);
          const data = await res.json();
          
          // 假進度條動畫 (直到 90%)
          setProgress(old => (old < 90 ? old + Math.random() * 10 : old));

          if (data.status === 'completed') {
            setStatus('completed');
            setProgress(100);
            clearInterval(intervalId);
          }
        } catch (err) {
          console.error("Status check failed", err);
        }
      }, 2000);
    }
    return () => clearInterval(intervalId);
  }, [status, taskId]);

  // --- Sync Logic ---
  const safePlay = async (videoElem) => {
    try {
      if (videoElem.paused) await videoElem.play();
    } catch (err) { /* ignore abort error */ }
  };

  const syncFunc = (action, source, target) => {
    if (isSyncing.current || !target.current) return;
    isSyncing.current = true;

    if (action === 'play') safePlay(target.current);
    else if (action === 'pause' && !target.current.paused) target.current.pause();
    else if (action === 'time') {
      if (Math.abs(target.current.currentTime - source.current.currentTime) > 0.1) {
        target.current.currentTime = source.current.currentTime;
      }
    }
    isSyncing.current = false;
  };
  // ------------------

  return (
    <div className="container">
      <header>
        <h1>AI Video Outpainting</h1>
        <p className="subtitle">基於 GAN 模型的視訊邊緣生成與擴展技術</p>
      </header>
      
      {/* 上傳區塊：只有在還沒完成時顯示，或者完成後想重新上傳 */}
      <div className="upload-card">
        <div className="file-input-wrapper">
          <span className="upload-icon">☁️</span>
          <p>{file ? `已選擇: ${file.name}` : "點擊或拖曳影片至此 (MP4, MOV)"}</p>
          <input type="file" accept="video/*" onChange={handleFileChange} />
        </div>
        
        <button 
          className="primary-btn"
          onClick={handleUpload} 
          disabled={!file || status === 'uploading' || status === 'processing'}
        >
          {status === 'uploading' ? '上傳中...' : status === 'processing' ? 'AI 運算中...' : '開始生成'}
        </button>

        {error && <div className="error-msg">{error}</div>}
      </div>

      {/* 進度條區塊 */}
      {status === 'processing' && (
        <div className="progress-container">
          <p style={{marginBottom: '10px'}}>正在進行畫面擴充與修復...</p>
          <div className="progress-bar-bg">
            <div className="progress-bar-fill" style={{ width: `${progress}%` }}></div>
          </div>
          <p style={{fontSize: '0.8rem', color: '#666', marginTop: '5px'}}>{Math.round(progress)}%</p>
        </div>
      )}

      {/* 結果區塊 */}
      {status === 'completed' && (
        <div className="result-section">
          <div style={{textAlign: 'center', marginBottom: '20px'}}>
            <h2 style={{margin: 0}}>Processing Complete</h2>
            <p style={{color: 'var(--accent-color)'}}>✨ 擴展成功</p>
          </div>
          
          <div className="video-grid">
            <div className="video-card">
              <div className="video-label">Input (256x256)</div>
              <video 
                ref={vid1Ref}
                src={videoUrls.original} 
                controls 
                muted // 靜音通常比較不會有自動播放問題
                onPlay={() => syncFunc('play', vid1Ref, vid2Ref)}
                onPause={() => syncFunc('pause', vid1Ref, vid2Ref)}
                onTimeUpdate={() => syncFunc('time', vid1Ref, vid2Ref)}
                onSeeking={() => syncFunc('time', vid1Ref, vid2Ref)}
              />
            </div>
            <div className="video-card">
              <div className="video-label" style={{color: 'var(--accent-color)'}}>Output (300x300)</div>
              <video 
                className="video-expanded"
                ref={vid2Ref}
                src={videoUrls.processed} 
                controls 
                muted
                onPlay={() => syncFunc('play', vid2Ref, vid1Ref)}
                onPause={() => syncFunc('pause', vid2Ref, vid1Ref)}
                onTimeUpdate={() => syncFunc('time', vid2Ref, vid1Ref)}
                onSeeking={() => syncFunc('time', vid2Ref, vid1Ref)}
              />
            </div>
          </div>
          
          <div style={{textAlign: 'center', marginTop: '30px'}}>
            <button className="primary-btn" onClick={() => {
              setStatus('idle');
              setFile(null);
              setVideoUrls({original: '', processed: ''});
            }}>
              處理新的影片
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
