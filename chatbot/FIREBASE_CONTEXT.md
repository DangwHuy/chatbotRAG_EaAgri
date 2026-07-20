# Tích hợp Nhật ký nông hộ vào Chatbot

Backend đã hỗ trợ nhận `userId` từ Flutter, đọc dữ liệu Firestore và tiêm vào prompt trước khi gọi LLM.

## 1. Cài dependencies

```bash
pip install -r chatbot/requirements.txt
```

Nếu bạn đang chạy lệnh từ bên trong thư mục `chatbot`, dùng:

```bash
pip install -r requirements.txt
```

## 2. Tạo Firebase service account

Vào Firebase Console > Project Settings > Service Accounts > Firebase Admin SDK > Generate new private key.

Lưu file JSON vào một trong các vị trí sau:

```text
serviceAccountKey.json
chatbot/serviceAccountKey.json
*firebase-adminsdk*.json
```

Hoặc đặt đường dẫn rõ trong file `.env`:

```env
FIREBASE_SERVICE_ACCOUNT_PATH=chatbot/serviceAccountKey.json
FARM_DIARY_LIMIT=24
FARM_DIARY_CONTEXT_LIMIT=8
FARM_CONTEXT_MAX_CHARS=4200
```

Không đưa file service account key vào Flutter và không commit lên Git. Repo đã thêm các pattern key này vào `.gitignore`.

## 3. Firestore schema backend đang đọc

Địa chỉ vườn:

```text
users/{userId}/farmAddress/{addressDoc}
```

Nhật ký nông hộ:

```text
farm_diary/{userId}/entries/{entryDoc}
```

Nhật ký được sắp xếp theo field `date` giảm dần và mặc định quét 24 bản ghi gần nhất.
Backend sẽ lọc theo câu hỏi rồi chỉ đưa tối đa 8 nhật ký liên quan nhất vào prompt. Cách này giúp AI liên kết được bệnh/triệu chứng với hoạt động chăm sóc gần đây nhưng vẫn tiết kiệm token.

## 4. Payload Flutter gửi lên `/api/chat`

```dart
final uid = FirebaseAuth.instance.currentUser?.uid;

final response = await http.post(
  Uri.parse('$apiBaseUrl/api/chat'),
  headers: {'Content-Type': 'application/json'},
  body: jsonEncode({
    'prompt': message,
    'userId': uid,
    'modelProvider': 'gemini',
    'history': chatHistory,
  }),
);
```

Backend cũng nhận các tên field tương đương như `question`, `message`, `user_id`, `uid`, `firebaseUid`.

## 5. Cách prompt được ghép

Mỗi lượt chat sẽ có dạng:

```text
Ngữ cảnh vườn từ app:
Địa chỉ vườn:
- ...

Nhật ký nông hộ gần đây:
- ...

Tài liệu tham khảo:
[Nguồn: ...pdf]
...

Câu hỏi của người dùng: ...
```

LLM được dặn dùng nhật ký như dữ liệu cá nhân hóa, còn tài liệu PDF vẫn là nguồn kỹ thuật để trích dẫn.

## 6. Hỏi lại khi thiếu dữ kiện

Với câu hỏi bệnh cây hoặc hiện tượng bất thường, backend yêu cầu AI phân tích câu hỏi trước, lọc nhật ký liên quan rồi mới trả lời.
Nếu chưa đủ dữ kiện để đưa phác đồ chắc chắn, AI sẽ thêm mục:

```text
Cần hỏi thêm:
- Lá rụng là lá non hay lá già?
- Đất quanh gốc có bị úng hoặc mùi thối rễ không?
```

API trả thêm `needs_follow_up`, `follow_up_questions` và `follow_up_options`.
Flutter dùng `follow_up_options` để hiện mỗi câu hỏi kèm 3-4 lựa chọn nhanh; người dùng bấm chọn là gửi lượt trả lời bổ sung cho AI.
Mỗi câu trả lời AI được giới hạn tối đa 100 từ để giảm chi phí và tránh dài dòng.
