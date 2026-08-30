
Tài Liệu Kiến Trúc Hệ Thống: Chatbot Nông Nghiệp Ea Agri (RAG)
Tài liệu này được soạn thảo dựa trên cấu trúc arc42 kết hợp với Mô hình C4 (C4 Model) nhằm minh bạch hóa kiến trúc, thiết kế và các quyết định kỹ thuật của dự án Chatbot Ea Agri, tuân thủ đúng các nguyên tắc chuẩn mực đã được đề ra trong Hướng dẫn Lập Báo cáo Phần mềm.

1. Giới thiệu và Mục tiêu (Introduction & Goals)
Động lực phát triển: Ea Agri Chatbot là trợ lý AI nông nghiệp chuyên sâu (đặc biệt tập trung vào cây sầu riêng), giúp bà con nông dân có thể tra cứu kỹ thuật canh tác, chẩn đoán bệnh cây trồng và nhận phác đồ điều trị trực tiếp khi đang ở ngoài đồng.

Mục tiêu chất lượng hàng đầu:

Tính chính xác (Functional Suitability): Phản hồi dựa trên tài liệu RAG chính thống và bám sát nhật ký canh tác của từng mảnh vườn (Firestore).
Hiệu suất (Performance): Trả lời ngắn gọn, nhanh chóng, phân tách rõ luồng Tiêu chuẩn (Standard) và Chuyên sâu (Expert).
Tính bảo mật (Security): Toàn bộ API phải được xác thực qua Firebase Token hoặc X-API-Key.
2. Ràng buộc (Constraints)
Ràng buộc công nghệ: Backend phát triển bằng Python (FastAPI). Sử dụng API mô hình ngôn ngữ bên ngoài (Google Gemini, DeepSeek).
Ràng buộc chi phí: Hạn chế số lượng token API (Tự động bỏ qua quá trình nhúng nếu không phát hiện PDF mới, giới hạn số lượng DIARY_CONTEXT_LIMIT để giảm độ dài bối cảnh).
Ràng buộc trải nghiệm (Usability): Nông dân không thích đọc dài. Câu trả lời của hệ thống bị giới hạn tối đa 150-250 chữ, sử dụng gạch đầu dòng và buộc phải gợi ý các tùy chọn tiếp theo (Follow-up Options) để người dùng dễ dàng bấm chọn.
3. Ngữ cảnh và Phạm vi (Context & Scope) - C4 Context Level
Góc nhìn tổng quan (Big Picture) thể hiện hệ thống dưới dạng hộp đen tương tác với người dùng và các dịch vụ ngoại vi.

⚠️ Failed to render Mermaid diagram: Invalid mermaid header: "C4Context". Expected "graph TD", "flowchart LR", "stateDiagram-v2", etc.. Supported types: flowchart/graph, stateDiagram-v2, sequenceDiagram, classDiagram, erDiagram, xychart-beta.
C4Context
    title C4 Context Diagram: Ea Agri Chatbot System

    Person(farmer, "Bà con nông dân", "Người dùng sử dụng ứng dụng di động để hỏi đáp kỹ thuật canh tác và bệnh cây trồng")
    
    System(chatbot, "Ea Agri Chatbot Backend", "Cung cấp câu trả lời AI chính xác, phân tích nhật ký vườn và gợi ý phác đồ điều trị")
    
    System_Ext(gemini, "Google Gemini API", "Mô hình LLM và Embedding cho xử lý ngôn ngữ")
    System_Ext(deepseek, "DeepSeek API", "Mô hình LLM chuyên gia")
    System_Ext(firebase, "Firebase (Auth & Firestore)", "Xác thực người dùng, lưu trữ danh sách vườn, nhật ký canh tác và danh sách dịch bệnh")

    Rel(farmer, chatbot, "Đặt câu hỏi & nhận tư vấn", "HTTPS")
    Rel(chatbot, gemini, "Gửi prompt, nhận text/embedding", "HTTPS/REST")
    Rel(chatbot, deepseek, "Gửi prompt chuyên sâu, nhận text", "HTTPS/REST")
    Rel(chatbot, firebase, "Xác thực Token & Truy vấn dữ liệu vườn", "HTTPS/REST")
Mermaid diagram
4. Chiến lược Giải pháp (Solution Strategy)
Để đạt được các mục tiêu trên, hệ thống sử dụng các chiến lược sau:

Kiến trúc RAG: Áp dụng mô hình Retrieval-Augmented Generation (RAG) kết hợp cơ sở dữ liệu Vector cục bộ (ChromaDB) để không bị ảo giác AI, luôn có nguồn tham chiếu tài liệu nội bộ.
Phân loại Ý định Thông minh (Intent Router): Dùng LLM đánh giá sơ bộ tin nhắn để chặn luồng hội thoại, phân loại thành: GREETING, FARM_QUERY, FARM_INFO, DISEASE_DIAGNOSIS. Việc này giúp hệ thống quyết định có nên tốn thời gian truy vấn Vector DB và Firestore hay không.
Cá nhân hóa theo Nhật ký Vườn (Farm Context Scoring): Lấy danh sách vườn (farms) và nhật ký hoạt động (farm_diary) từ Firestore. Hệ thống có cơ chế chấm điểm (scoring) từng hoạt động, rút trích các hoạt động rủi ro (bón phân sai, ngập úng) hoặc mới nhất làm bối cảnh cá nhân hóa cho LLM chẩn đoán.
5. Góc nhìn Khối Xây dựng (Building Block View) - C4 Container Level
Phân rã hệ thống thành các module thực thi kỹ thuật.

⚠️ Failed to render Mermaid diagram: Invalid mermaid header: "C4Container". Expected "graph TD", "flowchart LR", "stateDiagram-v2", etc.. Supported types: flowchart/graph, stateDiagram-v2, sequenceDiagram, classDiagram, erDiagram, xychart-beta.
C4Container
    title C4 Container Diagram: Ea Agri Chatbot System

    Person(farmer, "Bà con nông dân", "Client App")

    System_Boundary(c1, "Ea Agri Chatbot System") {
        Container(api, "FastAPI Server", "Python (api_server.py)", "Cung cấp endpoint /api/chat, xử lý router ý định, trích xuất tùy chọn câu hỏi")
        Container(rag, "RAG Engine", "Langchain, Python", "Quản lý Document Loader, Text Splitter, và LLM Invocation (run_agriculture_bot.py)")
        ContainerDb(chroma, "Chroma Vector DB", "ChromaDB", "Lưu trữ vector cục bộ tại vector_db_agri_gemini/")
        Container(context_engine, "Farm Context Builder", "Python (farm_context.py)", "Kết nối Firestore, chấm điểm và trích xuất nhật ký liên quan bằng thuật toán heuristic")
    }

    System_Ext(firebase, "Firebase Services", "Auth & Firestore")
    System_Ext(llm, "LLM APIs", "Gemini / DeepSeek")

    Rel(farmer, api, "Gọi API /api/chat (Header: X-Firebase-Token)", "HTTPS/JSON")
    Rel(api, firebase, "Xác thực Token")
    Rel(api, context_engine, "Yêu cầu Ngữ cảnh Vườn (nếu hỏi bệnh/vườn)")
    Rel(context_engine, firebase, "Query collection 'farms', 'farm_diary', 'pest_diseases'")
    Rel(api, rag, "Gửi câu hỏi + Ngữ cảnh")
    Rel(rag, chroma, "Tìm kiếm kNN (k=4/6)")
    Rel(rag, llm, "Generate Text")
Mermaid diagram
6. Góc nhìn Triển khai (Deployment View)
API Server: Tiến trình ASGI (Uvicorn) chạy trên một máy chủ Linux/Cloud VM.
Lưu trữ Cục bộ (Local File System):
Thư mục knowledge-base/: Chứa các tệp PDF tài liệu nông nghiệp.
Thư mục vector_db_agri_gemini/: Cơ sở dữ liệu Vector tĩnh (sqlite & parquet format).
Tệp *firebase-adminsdk*.json: Khóa bảo mật để kết nối SDK Admin Firebase.
Môi trường (.env): Lưu trữ các biến nhạy cảm như GOOGLE_API_KEY, DEEPSEEK_API_KEY, API_SECRET_KEY.
7. Khái niệm Xuyên suốt (Cross-cutting Concepts)
Bảo mật (Security): Endpoint chính /api/chat được bảo vệ bằng lớp HTTPBearer. Hệ thống giải mã JWT Token qua firebase_admin.auth.verify_id_token(). Có hỗ trợ X-API-Key fallback cho việc test/internal service.
Tối ưu Hậu xử lý (Post-processing): Áp dụng regex cắt lọc tự động (function compact_answer, remove_source_lines, extract_follow_up_questions) để trích xuất các nguồn tham chiếu và bộ gợi ý ra JSON riêng biệt, giúp Client UI hiển thị sạch đẹp.
Cơ chế Fallback (Kháng lỗi): Nếu người dùng không chỉ định model_provider hợp lệ, hệ thống tự động fallback về model chuẩn (gemini).
8. Rủi ro và Nợ Kỹ thuật (Risks and Technical Debt)
Rủi ro Dữ liệu Vector DB: ChromaDB đang lưu trực tiếp trên ổ cứng server (persist_directory). Khi tải trọng lớn và cần mở rộng ra nhiều server (horizontally scale), dữ liệu vector sẽ khó đồng bộ. Giải pháp đề xuất: Chuyển sang dịch vụ Managed Vector DB trên Cloud (VD: Pinecone, Qdrant) hoặc chạy Chroma ở dạng Docker riêng biệt.
Độ trễ của Intent Router (Latency): Việc sử dụng LLM để phân loại Intent trước vòng RAG chính làm tăng độ trễ tổng thể (latency) thêm khoảng 1-2 giây cho mỗi request.
Nợ Kỹ thuật (Context Window Bloat): Ngay cả khi đã giới hạn 8 bản ghi nhật ký, các ghi chú dài có thể làm tràn bộ nhớ ngữ cảnh. Giải pháp đề xuất: Áp dụng cơ chế tóm tắt tự động (Summarization) theo tuần/tháng trên Firestore thay vì kéo trực tiếp dữ liệu thô.
Kiểm thử (Testing): Thiếu vắng hoàn toàn các bài kiểm thử tự động (Unit Tests) cho các file api_server.py và farm_context.py, có nguy cơ lỗi logic khi bảo trì bảo dưỡng theo chuẩn (ISO 25010 Maintainability).
