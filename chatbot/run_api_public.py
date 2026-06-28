import os
import uvicorn
from pyngrok import ngrok
from dotenv import load_dotenv

def start_server():
    # 1. Xác thực với Ngrok bằng Token của bạn (tải từ file .env để bảo mật)
    load_dotenv()
    NGROK_AUTH_TOKEN = os.getenv("NGROK_AUTH_TOKEN")
    if not NGROK_AUTH_TOKEN:
        print("LỖI: Chưa có NGROK_AUTH_TOKEN trong file .env!")
        return
        
    ngrok.set_auth_token(NGROK_AUTH_TOKEN)

    # 2. Tạo đường hầm (tunnel) kết nối cổng 8000 ra ngoài Internet
    public_url = ngrok.connect(8000).public_url
    print("\n" + "="*60)
    print("🚀 THÀNH CÔNG! HỆ THỐNG ĐÃ ONLINE 🚀")
    print("="*60)
    print(f"🌍 Link gốc API:         {public_url}")
    print(f"👉 Link gọi Chatbot:     {public_url}/api/chat")
    print(f"📖 Xem tài liệu Test API: {public_url}/docs")
    print("="*60 + "\n")
    
    # 3. Chạy server FastAPI ở cổng 8000
    uvicorn.run("api_server:app", host="127.0.0.1", port=8000)

if __name__ == "__main__":
    start_server()
