# llmprojects

Trước khi bắt đầu: Nếu bạn gặp bất kỳ vấn đề nào hoặc có ý tưởng đóng góp để cải thiện và phát triển hơn, liên hệ với mình qua email: timiofficial.vn@gmail.com

Chúng ta sẽ bắt đầu bằng việc cài đặt Ollama

## 1. Cài đặt Ollama

1. Tải xuống và cài đặt Ollama từ https://ollama.com
   
📌 Lưu ý: Trên PC, bạn có thể cần quyền admin để cài đặt thành công.

2. Mở giao diện dòng lệnh:
   
Trên Windows: Nhấn Win + R, gõ cmd, rồi nhấn Enter.

Trên Mac: Mở Terminal (Applications > Utilities > Terminal).

3. Chạy mô hình:
   
Run `ollama run llama3.2` , đối với máy yếu hơn `ollama run llama3.2:1b`

🚫 Tránh sử dụng mô hình mới nhất `llama3.3` của Meta vì nó có 70B tham số, quá lớn với hầu hết máy tính cá nhân!

Nếu không hoạt động, thử chạy máy chủ: Trên Windows (Powershell) hoặc Mac (Terminal): `ollama serve`  

Sau đó thử lại bước 3.

## 2. Setup Environment

Sau đó, thực hiện các bước cài đặt như sau:

- Nếu bạn dùng PC vui lòng làm theo hướng dẫn trong file: `setup-pc.md`
- Nếu bạn dùng Mac vui lòng làm theo hướng dẫn trong file: `setup-mac.md`

   
