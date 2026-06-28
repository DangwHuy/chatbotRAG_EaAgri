import os
import glob
import shutil
from dotenv import load_dotenv
import gradio as gr
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_chroma import Chroma
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

# Load environment variables
load_dotenv(override=True)
os.environ['GOOGLE_API_KEY'] = os.getenv('GOOGLE_API_KEY', '')

# Config
MODEL = "gemini-2.5-flash"
db_name = "vector_db_agri_gemini"

def initialize_rag():
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2")

    base_folder = "knowledge-base"
    vectorstore = Chroma(persist_directory=db_name, embedding_function=embeddings)
    
    # Lấy danh sách các file đã được nhúng trong DB
    existing_data = vectorstore.get(include=["metadatas"])
    existing_sources = set()
    for meta in existing_data.get("metadatas", []):
        if meta and "source" in meta:
            existing_sources.add(os.path.normpath(meta["source"]))
            
    # Quét thư mục TẤT CẢ các thư mục con để tìm file PDF mới
    from langchain_community.document_loaders import PyPDFLoader
    pdf_files = glob.glob(os.path.join(base_folder, "**", "*.pdf"), recursive=True)
    new_documents = []
    
    for pdf_file in pdf_files:
        norm_path = os.path.normpath(pdf_file)
        if norm_path not in existing_sources:
            print(f"📄 Phát hiện tài liệu mới: {os.path.basename(pdf_file)}")
            loader = PyPDFLoader(pdf_file)
            new_documents.extend(loader.load())
            
    if new_documents:
        print(f"Tổng số trang mới cần học: {len(new_documents)}")
        print("Đang chia nhỏ văn bản (Chunking)...")
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        chunks = text_splitter.split_documents(new_documents)
        print(f"Đã tạo ra {len(chunks)} chunks mới")
        
        print("Đang gửi dữ liệu mới cho Gemini nhúng (Vui lòng chờ)...")
        vectorstore.add_documents(chunks)
        print("✅ Đã cập nhật xong dữ liệu mới vào hệ thống!")
    else:
        print("✅ Không có tài liệu nào mới, tự động bỏ qua bước nhúng để tiết kiệm 100% Token API...")

    print(f"Vectorstore đã sẵn sàng với tổng cộng {vectorstore._collection.count()} chunks")

    # Tăng số lượng tài liệu tham khảo (k) lên 5 để đảm bảo AI đọc đủ thông tin (rất quan trọng với bệnh phức tạp)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
    # Bỏ max_tokens để AI không bị ngắt câu giữa chừng
    llm = ChatGoogleGenerativeAI(temperature=0.3, model=MODEL)
    
    return retriever, llm

def run_ui():
    print("Đang thiết lập hệ thống AI...")
    try:
        retriever, llm = initialize_rag()
    except Exception as e:
        print(f"Lỗi khởi tạo hệ thống: {e}")
        return

    system_template = """Bạn là Trợ lý AI nông nghiệp của dự án Ea Agri.
Hãy xưng hô là "tôi" hoặc "Ea Agri", và gọi người dùng là "bà con" hoặc "bạn" một cách tự nhiên, gần gũi, không máy móc.
Dựa vào tài liệu dưới đây, hãy trả lời câu hỏi ĐÚNG TRỌNG TÂM, VÀO THẲNG VẤN ĐỀ, NGẮN GỌN để bà con dễ hiểu.
Tuyệt đối KHÔNG liệt kê dài dòng nếu không cần thiết.
Nếu trong tài liệu tham khảo KHÔNG CÓ CÂU TRẢ LỜI, hãy nói rõ: "Dạ, phần này Ea Agri chưa có tài liệu hướng dẫn cụ thể, bà con thông cảm nhé." Tuyệt đối không tự bịa ra thông tin nếu tài liệu không nhắc tới."""

    def chat(question, history):
        # Kết hợp câu hỏi hiện tại với câu hỏi trước đó để giữ ngữ cảnh tìm kiếm tài liệu
        search_query = question
        if history:
            last_msg = history[-1]
            if isinstance(last_msg, dict) and last_msg.get("role") == "user":
                search_query = last_msg.get("content", "") + " - " + question
            elif isinstance(last_msg, (list, tuple)) and len(last_msg) == 2:
                search_query = last_msg[0] + " - " + question
                
        docs = retriever.invoke(search_query)
        
        # Trích xuất tên các file làm nguồn tham khảo
        context_parts = []
        source_names = set()
        for doc in docs:
            # Lấy tên file gốc từ metadata
            source_file = os.path.basename(doc.metadata.get("source", "Tài liệu ẩn"))
            source_names.add(source_file)
            context_parts.append(f"[Nguồn: {source_file}]\n{doc.page_content}")
            
        context = "\n\n".join(context_parts)
        prompt = f"Tài liệu tham khảo:\n{context}\n\nCâu hỏi của người dùng: {question}"
        
        messages = [SystemMessage(content=system_template)]
        for msg in history:
            if isinstance(msg, dict):
                if msg.get("role") == "user":
                    messages.append(HumanMessage(content=msg.get("content", "")))
                elif msg.get("role") == "assistant":
                    messages.append(AIMessage(content=msg.get("content", "")))
            elif isinstance(msg, (list, tuple)) and len(msg) == 2:
                messages.append(HumanMessage(content=msg[0]))
                messages.append(AIMessage(content=msg[1]))
                
        messages.append(HumanMessage(content=prompt))
        response = llm.invoke(messages)
        
        # Nối thêm trích dẫn nguồn vào cuối câu trả lời
        sources_str = ", ".join(source_names)
        return response.content + f"\n\n*(Nguồn tham khảo: {sources_str})*"

    print("Đang khởi chạy giao diện Chatbot...")
    # Loại bỏ tham số type="messages" không còn được hỗ trợ trên Gradio v6
    view = gr.ChatInterface(
        fn=chat, 
        title="🌿 Chuyên Gia AI Nông Nghiệp (Gemini)",
        description="Trợ lý AI tư vấn kỹ thuật canh tác sầu riêng. Năng lượng bởi Google Gemini."
    ).launch(inbrowser=True)

if __name__ == "__main__":
    run_ui()
