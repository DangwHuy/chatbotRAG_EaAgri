import os
import json
import socket
import sys
from urllib.request import urlopen

import uvicorn
from pyngrok import ngrok, conf
from dotenv import load_dotenv


def configure_console():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def is_port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex((host, port)) == 0


def find_existing_tunnel(port: int):
    try:
        with urlopen("http://127.0.0.1:4040/api/tunnels", timeout=3) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None

    for tunnel in data.get("tunnels", []):
        addr = str(tunnel.get("config", {}).get("addr", "")).lower()
        if addr in {f"http://localhost:{port}", f"http://127.0.0.1:{port}"} or addr.endswith(f":{port}"):
            return tunnel.get("public_url")

    return None


def print_links(public_url: str):
    print("\n" + "="*60)
    print("🚀 THÀNH CÔNG! HỆ THỐNG ĐÃ ONLINE 🚀")
    print("="*60)
    print(f"🌍 Link gốc API:         {public_url}")
    print(f"👉 Link gọi Chatbot:     {public_url}/api/chat")
    print(f"📖 Xem tài liệu Test API: {public_url}/docs")
    print("="*60 + "\n")


def start_server():
    configure_console()

    # 1. Xác thực với Ngrok bằng Token của bạn (tải từ file .env để bảo mật)
    load_dotenv()
    NGROK_AUTH_TOKEN = os.getenv("NGROK_AUTH_TOKEN")
    if not NGROK_AUTH_TOKEN:
        print("LỖI: Chưa có NGROK_AUTH_TOKEN trong file .env!")
        return
        
    # Tăng thời gian chờ (timeout) cho ngrok nếu mạng chậm
    conf.get_default().request_timeout = 30
    ngrok.set_auth_token(NGROK_AUTH_TOKEN)

    # 2. Tạo đường hầm (tunnel) kết nối cổng 8000 ra ngoài Internet
    public_url = find_existing_tunnel(8000)
    if not public_url:
        public_url = ngrok.connect(8000).public_url

    print_links(public_url)

    if is_port_in_use("127.0.0.1", 8000):
        print("ℹ️  Server FastAPI ở cổng 8000 đang chạy sẵn, không khởi động thêm tiến trình mới.")
        print("Nếu muốn nạp code mới, hãy dừng server cũ trước rồi chạy lại lệnh này.")
        return
    
    # 3. Chạy server FastAPI ở cổng 8000
    uvicorn.run("api_server:app", host="127.0.0.1", port=8000)

if __name__ == "__main__":
    start_server()
