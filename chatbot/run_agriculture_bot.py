import os
import glob
import shutil
from types import SimpleNamespace
from dotenv import load_dotenv
import requests
try:
    import gradio as gr
except ModuleNotFoundError:
    gr = None
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_chroma import Chroma
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

# Load environment variables
load_dotenv(override=True)
os.environ['GOOGLE_API_KEY'] = os.getenv('GOOGLE_API_KEY', '')

# Config
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
db_name = "vector_db_agri_gemini"


class DeepSeekChat:
    def __init__(self, model: str, temperature: float = 0.3):
        self.model = model
        self.temperature = temperature
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = DEEPSEEK_BASE_URL.rstrip("/")

        if not self.api_key:
            raise ValueError("Chua co DEEPSEEK_API_KEY trong file .env")

    def _convert_message(self, message):
        message_type = message.__class__.__name__
        if message_type == "SystemMessage":
            role = "system"
        elif message_type == "AIMessage":
            role = "assistant"
        else:
            role = "user"

        return {"role": role, "content": message.content}

    def invoke(self, messages):
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "temperature": self.temperature,
                "messages": [self._convert_message(message) for message in messages],
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return SimpleNamespace(content=data["choices"][0]["message"]["content"])

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
        
        if len(chunks) > 0:
            print("Đang gửi dữ liệu mới cho Gemini nhúng (Vui lòng chờ)...")
            vectorstore.add_documents(chunks)
            print("✅ Đã cập nhật xong dữ liệu mới vào hệ thống!")
        else:
            print("⚠️ CẢNH BÁO: Tài liệu mới tải lên là file ảnh hoặc file rỗng (không có chữ dạng Text). Hệ thống đã bỏ qua.")
    else:
        print("✅ Không có tài liệu nào mới, tự động bỏ qua bước nhúng để tiết kiệm 100% Token API...")

    print(f"Vectorstore đã sẵn sàng với tổng cộng {vectorstore._collection.count()} chunks")

    # Lấy nhiều đoạn hơn một chút để giảm trường hợp tài liệu có nhưng retriever trả thiếu ngữ cảnh.
    retriever = vectorstore.as_retriever(search_kwargs={"k": 8})
    # Bỏ max_tokens để AI không bị ngắt câu giữa chừng
    llms = {
        "gemini": ChatGoogleGenerativeAI(temperature=0.3, model=GEMINI_MODEL),
        "deepseek": DeepSeekChat(temperature=0.3, model=DEEPSEEK_MODEL),
    }
    
    return retriever, llms

def run_ui():
    if gr is None:
        print("Chua cai gradio, khong the chay giao dien local. API FastAPI van co the hoat dong.")
        return

    print("Đang thiết lập hệ thống AI...")
    try:
        retriever, llms = initialize_rag()
    except Exception as e:
        print(f"Lỗi khởi tạo hệ thống: {e}")
        return

    system_template = """Bạn là Trợ lý AI nông nghiệp của dự án Ea Agri.
Hãy xưng hô là "tôi" hoặc "Ea Agri", và gọi người dùng là "bà con" hoặc "bạn" một cách tự nhiên.
Quy tắc xưng hô và mở đầu (CRITICAL GREETING RULE):
- Chỉ chào hỏi (ví dụ: "Chào bạn", "Chào bà con") ở lượt hội thoại đầu tiên khi mới bắt đầu hoặc khi người dùng chủ động chào.
- Trong các lượt chat/câu hỏi tiếp theo trong luồng hội thoại, TUYỆT ĐỐI KHÔNG lặp lại câu chào "Chào bạn", "Chào bà con" hay cấu trúc rập khuôn nữa!
- Hãy mở đầu linh hoạt, tự nhiên, đa dạng, không cố định, ví dụ như: "Dạ, Ea Agri xin giải đáp...", "Dạ đối với vấn đề này...", "Dạ thưa bà con...", "Ea Agri xin chia sẻ thêm...", hoặc đi thẳng luôn vào nhận định chuyên môn mà không cần rào đón.

Quy tắc trả lời:
1. Nếu người dùng chỉ chào hỏi ngắn (ví dụ: "Hi", "Chào bạn", "Cảm ơn"): Hãy đáp lại lịch sự, thân thiện và KHÔNG nhắc đến nguồn tham khảo.
2. Nếu người dùng hỏi kiến thức nông nghiệp có trong tài liệu RAG: Hãy dựa vào tài liệu được cung cấp dưới đây để trả lời ngắn gọn, đúng trọng tâm. Ở ĐÚNG CUỐI câu trả lời, BẮT BUỘC phải tự động thêm dòng trích dẫn nguồn theo đúng định dạng: `\n\n*(Nguồn tham khảo: tên_file.pdf)*`.
3. Khi kiến thức không có trong tài liệu RAG hoặc RAG trống: Bạn ĐƯỢC PHÉP mở rộng sử dụng kiến thức nông nghiệp chuyên môn tổng hợp (General AI Knowledge) để tư vấn đầy đủ cho bà con. Khi sử dụng kiến thức mở rộng bên ngoài, bắt buộc giải thích thân thiện: "Dạ, hiện trong kho dữ liệu của Ea Agri chưa ghi nhận chi tiết này, tuy nhiên theo kiến thức nông nghiệp thực tế..." và KHÔNG tự ghi nguồn tham khảo giả. Tuyệt đối không từ chối trả lời nếu câu hỏi thuộc lĩnh vực nông nghiệp!
"""

    def chat(question, history, model_provider="gemini"):
        selected_llm = llms.get(model_provider or "gemini", llms["gemini"])

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
        response = selected_llm.invoke(messages)
        return response.content

    print("Đang khởi chạy giao diện Chatbot...")
    # Loại bỏ tham số type="messages" không còn được hỗ trợ trên Gradio v6
    view = gr.ChatInterface(
        fn=chat, 
        title="🌿 Chuyên Gia AI Nông Nghiệp",
        description="Trợ lý AI tư vấn kỹ thuật canh tác sầu riêng.",
        additional_inputs=[
            gr.Dropdown(
                choices=["gemini", "deepseek"],
                value="gemini",
                label="Chon model"
            )
        ]
    ).launch(inbrowser=True)

if __name__ == "__main__":
    run_ui()
