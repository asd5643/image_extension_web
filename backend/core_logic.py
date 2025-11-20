import cv2
import numpy as np
import torch
from tqdm import tqdm
import os
import sys
import subprocess
import shutil

# ==========================================
# 1. 匯入你的模型 (請依據實際狀況修改)
# ==========================================
# sys.path.append(os.path.join(os.path.dirname(__file__), '..')) # 如果需要引用上一層目錄
# from model import Generator 

class VideoExpander:
    def __init__(self, model_path, device='cuda'):
        self.device = torch.device(device if torch.cuda.is_available() else 'cpu')
        print(f"Using device: {self.device}")
        
        # --- [TODO] 載入你的模型 ---
        # self.model = Generator().to(self.device)
        # checkpoint = torch.load(model_path, map_location=self.device)
        # self.model.load_state_dict(checkpoint)
        # self.model.eval()
        print("Model loaded (Mocking mode - input will pass through)")

    def preprocess(self, frame, input_res=(256, 256), output_res=(300, 300)):
        """
        1. Resize 原圖 -> 256x256
        2. Pad 到 -> 300x300
        """
        # 1. 強制 Resize 原始 Frame 到 256x256
        frame_resized = cv2.resize(frame, input_res)
        
        h_in, w_in = input_res
        h_out, w_out = output_res
        c = frame.shape[2]
        
        # 2. 建立 300x300 的畫布 (黑色背景)
        canvas = np.zeros((h_out, w_out, c), dtype=np.uint8)
        
        # 3. 計算置中位置
        # (300 - 256) // 2 = 22
        y_offset = (h_out - h_in) // 2
        x_offset = (w_out - w_in) // 2
        
        # 4. 將 256x256 的圖貼到 300x300 中心
        canvas[y_offset:y_offset+h_in, x_offset:x_offset+w_in] = frame_resized
        
        # 5. 轉成 Tensor, Normalize (-1 ~ 1)
        # OpenCV 是 BGR, 通常模型訓練用 RGB，這裡視你的訓練狀況而定
        # canvas_rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB) 
        input_tensor = torch.from_numpy(canvas).permute(2, 0, 1).float() / 255.0
        input_tensor = (input_tensor - 0.5) * 2.0 
        
        return input_tensor.unsqueeze(0).to(self.device), (x_offset, y_offset, w_in, h_in, frame_resized)

    def infer_frame(self, frame, input_res=(256, 256), output_res=(300, 300)):
        # 1. 預處理 (Resize 256 -> Pad 300)
        input_tensor, (x, y, w, h, orig_resized) = self.preprocess(frame, input_res, output_res)
        
        # 2. 模型推論 (Input: 300x300 with mask -> Output: 300x300 filled)
        with torch.no_grad():
            # --- [TODO] 呼叫模型 ---
            # prediction = self.model(input_tensor)
            
            # [模擬]: 假設模型輸出
            generated = input_tensor 
            
        # 3. 後處理
        generated = generated.squeeze(0).permute(1, 2, 0).cpu().numpy()
        generated = (generated + 1.0) / 2.0 * 255.0
        generated = np.clip(generated, 0, 255).astype(np.uint8)
        
        # 4. 把原本 256x256 的中心貼回去 (保持原圖清晰度，除非你要 Super-Res)
        # 如果模型效果很好，這行可以註解掉，直接用生成的
        generated[y:y+h, x:x+w] = orig_resized
        
        return generated

    def process_video(self, input_path, expanded_output_path, resized_original_output_path):
        """
        處理整部影片 (修正版：修正 FFmpeg 檔名後綴問題)
        """
        # 檢查輸入檔案
        if not os.path.exists(input_path):
            print(f"錯誤: 找不到檔案 '{input_path}'")
            return

        # 1. 定義 OpenCV 用暫存檔名
        temp_expanded_cv = expanded_output_path.replace(".mp4", "_cv_temp.mp4")
        temp_resized_cv = resized_original_output_path.replace(".mp4", "_cv_temp.mp4")

        # 2. 定義 FFmpeg 用暫存檔名 
        # [關鍵修正] 必須以 .mp4 結尾，FFmpeg 才知道要輸出 MP4 格式
        # 舊寫法 (錯誤): temp_expanded_final = expanded_output_path + ".part"
        temp_expanded_final = expanded_output_path.replace(".mp4", "_part.mp4")
        temp_resized_final = resized_original_output_path.replace(".mp4", "_part.mp4")

        cap = cv2.VideoCapture(input_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps == 0: fps = 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        input_res = (256, 256) 
        output_res = (300, 300) 

        # OpenCV Writers
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out_expanded = cv2.VideoWriter(temp_expanded_cv, fourcc, fps, output_res)
        out_resized_original = cv2.VideoWriter(temp_resized_cv, fourcc, fps, input_res)
        
        print(f"Processing: {input_path}")
        
        for i, _ in tqdm(enumerate(range(total_frames)), total=total_frames):
            ret, frame = cap.read()
            if not ret: break
            
            result_frame_expanded = self.infer_frame(frame, input_res=input_res, output_res=output_res)
            out_expanded.write(result_frame_expanded)

            frame_resized_256 = cv2.resize(frame, input_res)
            out_resized_original.write(frame_resized_256)
            
            if i % 50 == 0:
                print(f"Processing frame {i}/{total_frames}...", flush=True)

        cap.release()
        out_expanded.release()
        out_resized_original.release()
        
        # 3. 使用 FFmpeg 轉碼
        print("Converting videos to H.264 for Web playback...")
        try:
            print(f"  - Converting Expanded Video to {temp_expanded_final}...")
            command_expanded = [
                "ffmpeg", "-y", "-i", temp_expanded_cv,
                "-vcodec", "libx264", "-pix_fmt", "yuv420p",
                "-an", 
                temp_expanded_final # 現在這是 xxx_part.mp4，FFmpeg 看得懂了
            ]
            subprocess.run(command_expanded, check=True)
            
            print(f"  - Converting Resized Original Video to {temp_resized_final}...")
            command_resized = [
                "ffmpeg", "-y", "-i", temp_resized_cv,
                "-vcodec", "libx264", "-pix_fmt", "yuv420p",
                "-an", 
                temp_resized_final
            ]
            subprocess.run(command_resized, check=True)

            # 4. 改名 (Atomic Rename)
            if os.path.exists(temp_expanded_final):
                os.rename(temp_expanded_final, expanded_output_path)
                print(f"  -> Renamed expanded video to: {expanded_output_path}")
            else:
                print(f"Error: FFmpeg output missing: {temp_expanded_final}")
                
            if os.path.exists(temp_resized_final):
                os.rename(temp_resized_final, resized_original_output_path)
                print(f"  -> Renamed resized video to: {resized_original_output_path}")
            else:
                print(f"Error: FFmpeg output missing: {temp_resized_final}")

            # 清理 OpenCV 暫存檔
            if os.path.exists(temp_expanded_cv): os.remove(temp_expanded_cv)
            if os.path.exists(temp_resized_cv): os.remove(temp_resized_cv)
                
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg failed with return code {e.returncode}")
            raise e
        except Exception as e:
            print(f"Video processing failed: {e}")
            import traceback
            traceback.print_exc()

        print("Done video processing.")

if __name__ == "__main__":
    # 確保這裡的檔名正確，並且檔案真的在該目錄下
    # 注意：直接執行此腳本時，路徑是相對於腳本位置的
    INPUT_FILE = "input_video.mp4" 
    EXPANDED_FILE = "output_expanded.mp4"
    RESIZED_FILE = "output_resized.mp4"
    MODEL_PATH = "checkpoints/best_model.pth"
    
    if os.path.exists(INPUT_FILE):
        expander = VideoExpander(model_path=MODEL_PATH)
        expander.process_video(INPUT_FILE, EXPANDED_FILE, RESIZED_FILE)
    else:
        print(f"請先準備測試影片: {INPUT_FILE}")