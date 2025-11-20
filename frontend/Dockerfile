# --- 階段 1: 建置 (Build) ---
FROM node:18-alpine as build

WORKDIR /app

# 複製 package.json 並安裝依賴
COPY package.json package-lock.json ./
RUN npm install

# 複製原始碼並執行打包 (會產生 dist 資料夾)
COPY . .
RUN npm run build

# --- 階段 2: 執行 (Run) ---
# 使用 Nginx 這種超輕量網頁伺服器
FROM nginx:alpine

# 把剛剛打包好的 dist 資料夾複製到 Nginx 的預設目錄
COPY --from=build /app/dist /usr/share/nginx/html

# 開放 80 Port (網頁預設)
EXPOSE 80

# 啟動 Nginx
CMD ["nginx", "-g", "daemon off;"]