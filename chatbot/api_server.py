import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional

# Import hàm khởi tạo từ file cũ để tận dụng logic có sẵn
from run_agriculture_bot import initialize_rag

app = FastAPI(
    title="Ea Agri Chatbot API",
    description="API Server cho Chatbot Nông nghiệp tích hợp Gemini",
    version="1.0"
)

# Biến toàn cục để lưu bộ nhớ AI
retriever = None
llm = None

system_template = """Bạn là Trợ lý AI nông nghiệp của dự án Ea Agri.
Hãy xưng hô là "tôi" hoặc "Ea Agri", và gọi người dùng là "bà con" hoặc "bạn" một cách tự nhiên, gần gũi, không máy móc.
Dựa vào tài liệu dưới đây, hãy trả lời câu hỏi ĐÚNG TRỌNG TÂM, VÀO THẲNG VẤN ĐỀ, NGẮN GỌN để bà con dễ hiểu.
Tuyệt đối KHÔNG liệt kê dài dòng nếu không cần thiết.
Nếu trong tài liệu tham khảo KHÔNG CÓ CÂU TRẢ LỜI, hãy nói rõ: "Dạ, phần này Ea Agri chưa có tài liệu hướng dẫn cụ thể, bà con thông cảm nhé." Tuyệt đối không tự bịa ra thông tin nếu tài liệu không nhắc tới."""

# Định nghĩa cấu trúc dữ liệu gửi lên và trả về
class ChatMessage(BaseModel):
    role: str # "user" hoặc "assistant"
    content: str

class ChatRequest(BaseModel):
    question: str
    history: Optional[List[ChatMessage]] = []

class ChatResponse(BaseModel):
    answer: str
    sources: List[str]

@app.on_event("startup")
async def startup_event():
    global retriever, llm
    print("Đang khởi tạo hệ thống AI cho FastAPI...")
    retriever, llm = initialize_rag()
    print("✅ Hệ thống AI đã sẵn sàng phục vụ App của bạn!")

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    if not retriever or not llm:
        raise HTTPException(status_code=500, detail="Hệ thống AI chưa sẵn sàng")

    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

    try:
        # 1. Tìm kiếm tài liệu (RAG)
        search_query = request.question
        if request.history:
            last_msg = request.history[-1]
            if last_msg.role == "user":
                search_query = last_msg.content + " - " + request.question
                
        docs = retriever.invoke(search_query)
        
        # 2. Xử lý nguồn tham khảo
        context_parts = []
        source_names = set()
        for doc in docs:
            source_file = os.path.basename(doc.metadata.get("source", "Tài liệu ẩn"))
            source_names.add(source_file)
            context_parts.append(f"[Nguồn: {source_file}]\n{doc.page_content}")
            
        context = "\n\n".join(context_parts)
        prompt = f"Tài liệu tham khảo:\n{context}\n\nCâu hỏi của người dùng: {request.question}"
        
        # 3. Tạo lịch sử tin nhắn
        messages = [SystemMessage(content=system_template)]
        for msg in request.history:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))
                
        messages.append(HumanMessage(content=prompt))
        
        # 4. Trả lời
        response = llm.invoke(messages)
        
        # Nối thêm trích dẫn nguồn vào cuối câu trả lời (giống bản Web)
        final_answer = response.content
        if source_names:
            sources_str = ", ".join(source_names)
            final_answer += f"\n\n*(Nguồn tham khảo: {sources_str})*"
            
        return ChatResponse(
            answer=final_answer,
            sources=list(source_names)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
