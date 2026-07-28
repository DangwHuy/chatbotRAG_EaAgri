import os
import re
from fastapi import Body, FastAPI, HTTPException, Query, Header, Security, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Any, Dict, List, Optional, Tuple

# Import hàm khởi tạo từ file cũ để tận dụng logic có sẵn
from farm_context import (
    fetch_farm_records,
    format_farm_context,
    get_farm_context,
    get_firestore_client,
    mask_user_id,
    fetch_disease_images,
)
from run_agriculture_bot import initialize_rag

app = FastAPI(
    title="Ea Agri Chatbot API",
    description="API Server cho Chatbot Nong nghiep tich hop Gemini va DeepSeek",
    version="1.0",
    docs_url=None if os.getenv("DISABLE_DOCS", "false").lower() == "true" else "/docs",
    redoc_url=None if os.getenv("DISABLE_DOCS", "false").lower() == "true" else "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Biến toàn cục để lưu bộ nhớ AI
retriever = None
llms = None

system_template = """Bạn là Trợ lý AI nông nghiệp của dự án Ea Agri.
Hãy xưng hô là "tôi" hoặc "Ea Agri", và gọi người dùng là "bà con" hoặc "bạn" một cách tự nhiên.
Quy tắc xưng hô và mở đầu (CRITICAL GREETING RULE):
- Chỉ chào hỏi (ví dụ: "Chào bạn", "Chào bà con") ở lượt hội thoại đầu tiên khi mới bắt đầu hoặc khi người dùng chủ động chào.
- Trong các lượt chat/câu hỏi tiếp theo trong luồng hội thoại, TUYỆT ĐỐI KHÔNG lặp lại câu chào "Chào bạn", "Chào bà con" hay cấu trúc rập khuôn nữa!
- Hãy mở đầu linh hoạt, tự nhiên, đa dạng, không cố định, ví dụ như: "Dạ, Ea Agri xin giải đáp...", "Dạ đối với vấn đề này...", "Dạ thưa bà con...", "Ea Agri xin chia sẻ thêm...", hoặc đi thẳng luôn vào nhận định chuyên môn mà không cần rào đón.

Quy tắc trả lời:
1. Nếu người dùng chỉ chào hỏi ngắn (ví dụ: "Hi", "Chào bạn", "Cảm ơn"): Hãy đáp lại lịch sự, thân thiện và KHÔNG nhắc đến nguồn tham khảo.
2. Nếu người dùng hỏi kiến thức nông nghiệp: Hãy dựa vào tài liệu được cung cấp dưới đây để trả lời ngắn gọn, đúng trọng tâm. Không cần tự ghi dòng nguồn; backend sẽ tự gắn nguồn tham khảo ở cuối.
3. Khi kiến thức không có trong "Tài liệu tham khảo" (RAG) hoặc RAG trống/không liên quan: Bạn ĐƯỢC PHÉP mở rộng sử dụng kiến thức nông nghiệp chuyên môn tổng hợp (General AI Knowledge) để tư vấn và giải đáp đầy đủ cho bà con. Khi sử dụng kiến thức mở rộng bên ngoài, hãy giải thích thân thiện: "Dạ, hiện trong kho dữ liệu của Ea Agri chưa ghi nhận chi tiết này, tuy nhiên theo kiến thức nông nghiệp thực tế..." hoặc "Theo kiến thức chuyên môn mở rộng...". Tuyệt đối không từ chối trả lời hoặc bỏ cuộc nếu câu hỏi liên quan đến nông nghiệp, cây trồng, phân bón hay sâu bệnh!
4. ĐỐI VỚI NHẬT KÝ VƯỜN (NGỮ CẢNH TỪ APP):
   - CHỈ nhắc đến hoặc trích dẫn nhật ký NẾU NÓ THỰC SỰ CÓ LIÊN QUAN mật thiết đến câu hỏi hoặc giúp ích cho việc chẩn đoán (ví dụ: vừa bón phân sai, phun thuốc quá liều, mưa ngập liên tục...).
   - Nếu nhật ký KHÔNG LIÊN QUAN hoặc chỉ ghi thông tin chung chung (ví dụ: "cây tốt", "làm cỏ", "thu hoạch", không có gì đặc biệt) thì TUYỆT ĐỐI BỎ QUA, không cần nhắc lại hay trích dẫn nhật ký vào câu trả lời để tránh dài dòng!
   - Khi có dữ liệu liên quan để phân tích, mới nói rõ "theo nhật ký" hoặc "trong thông tin vườn".
5. Không tiết lộ userId, cấu trúc database, khóa Firebase hoặc chi tiết kỹ thuật nội bộ.
6. Trả lời NGẮN GỌN, rõ ý, phần nội dung chính không vượt quá 150 từ tiếng Việt:
   - Nếu chưa đủ dữ kiện và cần hỏi thêm: tối đa 90 từ.
   - Nếu đã đủ dữ kiện để tư vấn: tối đa 150 từ.
   - Luôn xuống dòng cho dễ đọc, ưu tiên format:
     **Nhận định:** 1-2 câu.
     **Căn cứ:** 1-3 gạch đầu dòng ngắn từ RAG/nhật ký/kiến thức chuẩn.
     **Nên làm:** 1-2 gạch đầu dòng hành động.
   - Không liệt kê toàn bộ nhật ký; chỉ nhắc tối đa 3-5 hoạt động liên quan nhất.
   - Nếu người dùng hỏi "các hoạt động gần đây", chỉ tóm tắt tối đa 5 hoạt động mới nhất theo dạng gạch đầu dòng.
   - Kết thúc bằng 1-2 việc nên làm tiếp theo, không viết dài dòng.
   - Viết câu hoàn chỉnh, không dùng dấu `...` để kết thúc.
7. Khi người dùng hỏi về bệnh cây, rụng lá, vàng lá, sâu hại, thối rễ, sốc phân hoặc hiện tượng bất thường:
   - Trước hết xác định triệu chứng chính trong câu hỏi.
   - Sau đó đối chiếu với "Nhật ký nông hộ liên quan đến câu hỏi", đặc biệt các hoạt động vài ngày gần đây như bón phân, phun thuốc, tưới nước, mưa/ngập, cắt tỉa, quan sát.
   - Nêu tối đa 2-3 nguyên nhân khả nghi theo mức độ liên quan, không khẳng định chắc chắn nếu thiếu bằng chứng.
   - Nếu câu hỏi + nhật ký chưa đủ dữ kiện để chẩn đoán, hãy hỏi lại 1-3 câu ngắn, cụ thể.
   - Khi hỏi lại để làm rõ, đặt mục cuối cùng đúng tiêu đề `Cần hỏi thêm:` rồi liệt kê từng câu hỏi bằng gạch đầu dòng. Ngay trong mỗi câu hỏi, BẮT BUỘC gợi ý 2-4 lựa chọn trả lời ngắn gọn, liên quan mật thiết đến câu hỏi đó trong ngoặc vuông `[...]` (ví dụ: `- Bệnh xuất hiện ở mặt trên hay mặt dưới lá? [Mặt trên lá, Mặt dưới lá, Cả hai mặt]`, `- Vết bệnh lây lan nhanh hay chậm? [Rất nhanh, Chậm rải rác, Mới phát hiện]`).
   - Đưa hướng xử lý an toàn trước: ngưng bón/phun khi chưa rõ nguyên nhân, kiểm tra thoát nước, quan sát rễ/lá/thân, rồi mới đề xuất thuốc/phân nếu có căn cứ.
   - Chỉ đưa phác đồ điều trị chi tiết khi đã đủ thông tin; nếu chưa đủ, đưa biện pháp tạm thời an toàn và chờ người dùng trả lời thêm.
8. QUY TẮC NHỚ LỊCH SỬ HỘI THOẠI & PHÂN TÍCH TIẾP (CRITICAL MEMORY): Khi người dùng trả lời bổ sung thông tin cho các câu hỏi làm rõ trước đó (ví dụ có từ khóa 'Bổ sung thông tin:', 'Trả lời thêm:' hoặc các lựa chọn), BẮT BUỘC bạn phải ĐỌC LẠI toàn bộ các tin nhắn trước trong lịch sử (đặc biệt là triệu chứng ban đầu người dùng hỏi và phán đoán của bạn ở lượt trước). Hãy tổng hợp triệu chứng cũ + thông tin bổ sung mới để đưa ra Kết luận chẩn đoán chính xác và phác đồ điều trị cụ thể. KHÔNG ĐƯỢC hỏi lại những câu đã hỏi, và KHÔNG BẮT người dùng mô tả lại từ đầu!
9. Tài liệu RAG là căn cứ kỹ thuật ưu tiên số 1; nếu RAG thiếu thì linh hoạt bổ sung bằng kiến thức chuyên môn AI mở rộng; nhật ký nông hộ dùng để cá nhân hóa và suy luận tình huống.
"""

# Định nghĩa cấu trúc dữ liệu gửi lên và trả về
class ChatMessage(BaseModel):
    role: str # "user" hoặc "assistant"
    content: str

class ChatRequest(BaseModel):
    question: str
    history: Optional[List[ChatMessage]] = []
    model_provider: Optional[str] = "gemini"
    userId: Optional[str] = None
    user_id: Optional[str] = None


class FollowUpOption(BaseModel):
    question: str
    options: List[str]


class DiseaseImage(BaseModel):
    name: str
    imageUrl: str


class ChatResponse(BaseModel):
    answer: str
    sources: List[str]
    needs_follow_up: bool = False
    follow_up_questions: List[str] = []
    follow_up_options: List[FollowUpOption] = []
    images: List[DiseaseImage] = []


class FarmContextDebugResponse(BaseModel):
    enabled: bool
    user: str
    firebase_connected: bool
    farmAddress_docs: int
    diary_entries: int
    context_chars: int


def normalize_model_provider(payload: Any) -> str:
    raw_model = "gemini"
    if isinstance(payload, dict):
        raw_model = (
            payload.get("model_provider")
            or payload.get("modelProvider")
            or payload.get("model")
            or payload.get("llm")
            or payload.get("provider")
            or "gemini"
        )
    normalized = str(raw_model).lower().strip().replace(" ", "").replace("_", "").replace("-", "")

    if normalized in {"gemini", "google", "googleai"} or "gemini" in normalized:
        return "gemini"
    if normalized in {"deepseek", "deepseekchat", "deepseekv3"} or "deepseek" in normalized:
        return "deepseek"

    return normalized


def extract_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value).strip()
    if isinstance(value, list):
        parts = [extract_text(item) for item in value]
        return " ".join(part for part in parts if part).strip()
    if isinstance(value, dict):
        for key in ("text", "content", "message", "answer", "value", "input", "query", "prompt"):
            text = extract_text(value.get(key))
            if text:
                return text
        return extract_text(value.get("parts"))
    return str(value).strip()


def get_message_content(item: Dict[str, Any]) -> str:
    return extract_text(item)


def normalize_user_id(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""

    for key in (
        "userId",
        "user_id",
        "uid",
        "firebaseUid",
        "firebase_uid",
        "firebaseUserId",
    ):
        text = extract_text(payload.get(key))
        if text:
            return text

    for key in ("user", "auth", "firebaseUser", "account"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            text = normalize_user_id(nested)
            if text:
                return text

    return ""


def build_analysis_query(question: str, history: List[Dict[str, str]]) -> str:
    recent_messages = []
    for msg in history[-4:]:
        content = msg.get("content", "").strip()
        if content:
            recent_messages.append(content)

    recent_messages.append(question)
    return " - ".join(recent_messages)


def build_retrieval_query(question: str, history: List[Dict[str, str]]) -> str:
    clean_question = (question or "").strip()
    normalized = clean_question.lower()

    is_follow_up_answer = normalized.startswith("trả lời thêm:") or normalized.startswith("tra loi them:")
    if is_follow_up_answer:
        return build_analysis_query(clean_question, history)

    question_word_count = len(clean_question.split())
    if question_word_count <= 4:
        previous_user_messages = [
            msg.get("content", "").strip()
            for msg in history[-4:]
            if msg.get("role") == "user" and msg.get("content", "").strip()
        ]
        if previous_user_messages:
            return previous_user_messages[-1] + " - " + clean_question

    return clean_question


def _clean_follow_up_question(line: str) -> str:
    question = re.sub(r"^\s*[-*•\d.)]+\s*", "", line).strip()
    question = question.strip("`*_ ")
    return question


def extract_follow_up_questions(answer: str, limit: int = 3) -> List[str]:
    lines = answer.splitlines()
    questions = []
    in_follow_up_section = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_follow_up_section and questions:
                break
            continue

        normalized = stripped.lower().replace("*", "").replace("#", "").strip()
        if "cần hỏi thêm" in normalized or "can hoi them" in normalized:
            in_follow_up_section = True
            continue

        if in_follow_up_section:
            question = _clean_follow_up_question(stripped)
            if ("?" in question or len(question) > 10) and question not in questions:
                questions.append(question)
            if len(questions) >= limit:
                break

    if questions:
        return questions[:limit]

    for match in re.findall(r"([^?\n]{8,}\?(?:\s*\[[^\]]+\]|\s*\([^\)]+\))?)", answer):
        question = _clean_follow_up_question(match)
        if question and question not in questions:
            questions.append(question)
        if len(questions) >= limit:
            break

    return questions[:limit]


def _default_follow_up_options(question: str) -> List[str]:
    # 1. Ưu tiên trích xuất option nằm trong ngoặc vuông [...] hoặc (...) từ câu hỏi do AI tạo ra
    match = re.search(r"\[([^\]]+)\]|\(([^)]+)\)", question)
    if match:
        raw_opts = match.group(1) or match.group(2)
        opts = [o.strip() for o in re.split(r",|/|\|", raw_opts) if o.strip()]
        if len(opts) >= 2:
            return opts[:4]

    clean_q = re.sub(r"\[[^\]]*\]|\([^\)]*\)", "", question).strip().lower()

    # 2. Nhận diện ngữ nghĩa thông minh theo chuyên môn chẩn đoán bệnh nông nghiệp
    if any(k in clean_q for k in ("mặt trên", "mặt dưới", "hai mặt", "mặt lá")):
        return ["Mặt trên lá", "Mặt dưới lá", "Cả hai mặt lá", "Không rõ"]

    if any(k in clean_q for k in ("bộ phận", "vị trí", "ở đâu", "ngọn", "gốc", "thân", "cành")):
        return ["Ở lá non/ngọn", "Ở lá già/gốc", "Trên thân/cành", "Cả cây"]

    if any(k in clean_q for k in ("lá non", "lá già", "bánh tẻ")):
        return ["Lá non (đọt non)", "Lá già / lá bánh tẻ", "Cả lá non và già", "Không rõ"]

    if any(k in clean_q for k in ("màu sắc", "màu gì", "hình dạng", "sũng nước", "cháy bìa", "đốm")):
        return ["Đốm nâu/đen thâm", "Cháy khô mép lá", "Vàng sũng nước", "Không rõ"]

    if any(k in clean_q for k in ("rễ", "cổ rễ", "thối rễ", "nhớt")):
        return ["Rễ trắng khỏe", "Rễ nâu/thối", "Chưa đào kiểm tra", "Không rõ"]

    if any(k in clean_q for k in ("đất", "úng", "thoát nước", "ẩm")):
        return ["Đất ẩm úng/đọng nước", "Đất khô ráo bình thường", "Mới mưa nhiều", "Không rõ"]

    if any(k in clean_q for k in ("phân", "bón", "thuốc", "phun", "xử lý", "chăm sóc")):
        return ["Mới phun/bón gần đây", "Chưa xử lý gì", "Đã dùng nhưng không đỡ", "Không nhớ"]

    if any(k in clean_q for k in ("mấy ngày", "bao lâu", "khi nào", "từ bao giờ", "thời gian")):
        return ["Mới 1-2 ngày nay", "Khoảng 3-7 ngày", "Hơn 1 tuần rồi", "Không nhớ"]

    if any(k in clean_q for k in ("mức độ", "lan rộng", "tốc độ", "nhanh hay chậm", "nặng hay nhẹ")):
        return ["Mới xuất hiện nhẹ", "Đang lan trung bình", "Bị nặng nhiều cây", "Không rõ"]

    if any(k in clean_q for k in ("lô", "vườn", "mấy cây", "cây nào", "rải rác")):
        return ["Chỉ rải rác vài cây", "Bị cả lô / nhiều cây", "Lây lan cả vườn", "Không rõ"]

    if any(k in clean_q for k in ("có kèm theo", "có bị", "có phải", "đúng không", "chưa")):
        return ["Có hiện tượng này", "Không có", "Chưa để ý / Không rõ"]

    return ["Có", "Không", "Không rõ", "Cần kiểm tra thêm"]


def build_follow_up_options(questions: List[str]) -> List[Dict[str, Any]]:
    result = []
    for q in questions[:3]:
        opts = _default_follow_up_options(q)
        # Loại bỏ ngoặc vuông chứa option ra khỏi tiêu đề câu hỏi để hiển thị trên UI sạch đẹp hơn
        clean_q = re.sub(r"\s*(\[[^\]]*\]|\([^\)]*\))\s*$", "", q).strip()
        result.append({"question": clean_q, "options": opts})
    return result


def remove_source_lines(answer: str) -> str:
    lines = []
    for line in answer.splitlines():
        normalized = line.lower()
        if "nguồn tham khảo" in normalized or "nguon tham khao" in normalized:
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def remove_follow_up_section(answer: str) -> str:
    lines = []
    for line in answer.splitlines():
        normalized = line.lower().replace("*", "").replace("#", "").strip()
        if "cần hỏi thêm" in normalized or "can hoi them" in normalized:
            marker_match = re.search(r"cần hỏi thêm|can hoi them", line, flags=re.IGNORECASE)
            if marker_match:
                before_marker = line[:marker_match.start()].strip()
                if before_marker:
                    lines.append(before_marker)
            break
        lines.append(line)
    return "\n".join(lines).strip()


def _ensure_sentence_end(text: str) -> str:
    text = text.rstrip(" ,;:-")
    if text and text[-1] not in ".!?":
        text += "."
    return text


def compact_answer(answer: str, max_words: int = 150) -> str:
    clean_answer = remove_source_lines(answer).strip()
    words = clean_answer.split()
    if len(words) <= max_words:
        return clean_answer

    segments = re.split(r"(\n+)|(?<=[.!?])\s+", clean_answer)
    selected_segments = []
    selected_word_count = 0

    for segment in segments:
        if segment is None:
            continue
        if segment.startswith("\n"):
            if selected_segments and not selected_segments[-1].endswith("\n"):
                selected_segments.append(segment)
            continue

        segment = segment.strip()
        if not segment:
            continue

        segment_word_count = len(segment.split())
        if selected_segments and selected_word_count + segment_word_count > max_words:
            break
        if not selected_segments and segment_word_count > max_words:
            break

        selected_segments.append(segment)
        selected_word_count += segment_word_count

    if selected_segments:
        compact = ""
        for segment in selected_segments:
            if segment.startswith("\n"):
                compact = compact.rstrip() + segment
            elif compact.endswith("\n") or not compact:
                compact += segment
            else:
                compact += " " + segment
        compact = compact.strip()
    else:
        compact = " ".join(words[:max_words]).strip()

    return _ensure_sentence_end(compact)


def build_source_citation(source_names: set) -> str:
    visible_sources = sorted(source_names)[:3]
    if not visible_sources:
        return ""

    suffix = ""
    if len(source_names) > 3:
        suffix = f" và {len(source_names) - 3} tài liệu khác"

    return f"\n\n*(Nguồn tham khảo: {', '.join(visible_sources)}{suffix})*"


def is_greeting_question(question: str) -> bool:
    normalized = question.lower().strip()
    normalized = re.sub(r"[^\w\sà-ỹ]", " ", normalized)
    tokens = set(normalized.split())
    greeting_tokens = {"hi", "hello", "chào", "chao", "alo", "cảm", "cam", "ơn", "on"}
    return bool(tokens) and len(tokens) <= 5 and bool(tokens & greeting_tokens)


def should_append_sources(answer: str, source_names: set, question: str) -> bool:
    if not source_names:
        return False
    if is_greeting_question(question):
        return False

    normalized = answer.lower()
    no_doc_markers = [
        "chưa có tài liệu",
        "chua co tai lieu",
        "không có tài liệu",
        "khong co tai lieu",
        "không tìm thấy",
        "khong tim thay",
        "chưa ghi nhận",
        "chua ghi nhan",
        "trong kho dữ liệu",
        "trong kho du lieu",
        "kiến thức nông nghiệp thực tế",
        "kien thuc nong nghiep thuc te",
        "kiến thức chuyên môn mở rộng",
        "kien thuc chuyen mon mo rong",
        "theo kiến thức",
        "theo kien thuc",
    ]
    return not any(marker in normalized for marker in no_doc_markers)


def finalize_answer(
    answer: str,
    source_names: set,
    follow_up_questions: List[str],
    question: str,
) -> str:
    # Lược bỏ câu trả lời dư thừa bằng cách loại bỏ các dòng ghi nguồn và câu hỏi làm rõ do LLM tự sinh
    clean_answer = remove_source_lines(answer).strip()
    base_answer = remove_follow_up_section(clean_answer) if follow_up_questions else clean_answer
    final_answer = base_answer.strip()

    if should_append_sources(final_answer, source_names, question):
        final_answer += build_source_citation(source_names)

    return final_answer


def normalize_history(raw_history: Any) -> List[Dict[str, str]]:
    if isinstance(raw_history, dict):
        raw_history = (
            raw_history.get("history")
            or raw_history.get("messages")
            or raw_history.get("items")
            or raw_history.get("data")
            or []
        )
    if not isinstance(raw_history, list):
        return []

    history = []
    for item in raw_history:
        if isinstance(item, dict):
            raw_role = item.get("role") or item.get("sender") or item.get("type") or "user"
            role_value = str(raw_role).lower().strip()
            role = "assistant" if role_value in {"assistant", "ai", "bot"} else "user"
            content = get_message_content(item)
            if content:
                history.append({"role": role, "content": content})
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            user_content = str(item[0]).strip()
            assistant_content = str(item[1]).strip()
            if user_content:
                history.append({"role": "user", "content": user_content})
            if assistant_content:
                history.append({"role": "assistant", "content": assistant_content})
        elif isinstance(item, str):
            content = item.strip()
            if content:
                history.append({"role": "user", "content": content})

    return history


def split_question_from_messages(raw_messages: Any) -> Tuple[str, List[Dict[str, str]]]:
    messages = normalize_history(raw_messages)
    if not messages:
        return "", []

    for index in range(len(messages) - 1, -1, -1):
        if messages[index]["role"] == "user":
            question = messages[index]["content"]
            history = messages[:index]
            return question, history

    return "", messages


def normalize_chat_payload(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, str):
        question = payload.strip()
        if question:
            return {
                "question": question,
                "history": [],
                "model_provider": normalize_model_provider(payload),
                "user_id": "",
            }

    if isinstance(payload, list):
        question, history = split_question_from_messages(payload)
        if question:
            return {
                "question": question,
                "history": history,
                "model_provider": normalize_model_provider(payload),
                "user_id": "",
            }

    if not isinstance(payload, dict):
        payload = {}

    user_id = normalize_user_id(payload)
    raw_question = (
        payload.get("question")
        or payload.get("message")
        or payload.get("content")
        or payload.get("text")
        or payload.get("prompt")
        or payload.get("query")
        or payload.get("input")
        or payload.get("userMessage")
    )
    question = extract_text(raw_question)
    history = normalize_history(payload.get("history") or payload.get("chat_history") or [])

    if question and not history:
        history = normalize_history(payload.get("messages") or [])
        if history and history[-1]["role"] == "user" and history[-1]["content"] == question:
            history = history[:-1]

    if not question:
        question, history = split_question_from_messages(payload.get("messages"))

    if not question:
        for key in ("data", "body", "payload", "request", "variables", "input", "params", "args"):
            nested_payload = payload.get(key)
            if nested_payload:
                try:
                    nested = normalize_chat_payload(nested_payload)
                    if nested["question"]:
                        if not nested.get("user_id") and user_id:
                            nested["user_id"] = user_id
                        return nested
                except HTTPException:
                    pass

    if not question:
        print(f"[api/chat] Bad request. Khong tim thay cau hoi trong payload keys: {list(payload.keys())}")
        raise HTTPException(
            status_code=400,
            detail="Thieu noi dung cau hoi. Hay gui field question, message, hoac messages co tin nhan user."
        )

    return {
        "question": question,
        "history": history,
        "model_provider": normalize_model_provider(payload),
        "user_id": user_id,
    }

security = HTTPBearer(auto_error=False)

def verify_security(
    auth_credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
    x_firebase_token: Optional[str] = Header(None, alias="x-firebase-token")
):
    # 0. Nếu đang tắt bảo mật (để dev/test nội bộ)
    if os.getenv("DISABLE_SECURITY", "false").lower() == "true":
        return {"type": "disabled"}

    # 1. Kiểm tra API Key bí mật nội bộ (nếu có cấu hình API_SECRET_KEY trong .env)
    secret_key = os.getenv("API_SECRET_KEY", "").strip()
    if secret_key:
        if x_api_key == secret_key:
            return {"type": "api_key", "user": "trusted_client"}
        if auth_credentials and auth_credentials.credentials == secret_key:
            return {"type": "api_key", "user": "trusted_client"}

    # 2. Kiểm tra Firebase ID Token
    token = None
    if auth_credentials and auth_credentials.credentials:
        token = auth_credentials.credentials
    elif x_firebase_token:
        token = x_firebase_token
        
    if not token:
        raise HTTPException(
            status_code=401, 
            detail="Truy cập bị từ chối: Vui lòng gửi Firebase ID Token hoặc X-API-Key hợp lệ qua Header Authorization."
        )
        
    try:
        from farm_context import get_firestore_client
        get_firestore_client() # Đảm bảo firebase_admin đã khởi tạo
        
        import firebase_admin
        from firebase_admin import auth
        
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        print(f"[Security] Lỗi xác thực Firebase Token: {e}")
        raise HTTPException(status_code=401, detail=f"Token đăng nhập không hợp lệ hoặc đã hết hạn. Chi tiết lỗi từ server: {str(e)}")

@app.on_event("startup")
async def startup_event():
    global retriever, llms
    print("Đang khởi tạo hệ thống AI cho FastAPI...")
    retriever, llms = initialize_rag()
    print("✅ Hệ thống AI đã sẵn sàng phục vụ App của bạn!")

@app.post("/api/chat", response_model=ChatResponse, dependencies=[Depends(verify_security)])
async def chat_endpoint(payload: Any = Body(...)):
    if not retriever or not llms:
        raise HTTPException(status_code=500, detail="Hệ thống AI chưa sẵn sàng")

    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

    request = normalize_chat_payload(payload)
    requested_model = request["model_provider"]
    if requested_model not in llms:
        print(f"[api/chat] model_provider '{requested_model}' khong ho tro, tu dong dung gemini.")
        requested_model = "gemini"
    selected_llm = llms[requested_model]

    try:
        # 1. Tìm kiếm tài liệu (RAG)
        retrieval_query = build_retrieval_query(request["question"], request["history"])
        analysis_query = build_analysis_query(request["question"], request["history"])
                
        docs = retriever.invoke(retrieval_query)
        
        # 2. Xử lý nguồn tham khảo
        context_parts = []
        source_names = set()
        for doc in docs:
            source_file = os.path.basename(doc.metadata.get("source", "Tài liệu ẩn"))
            source_names.add(source_file)
            context_parts.append(f"[Nguồn: {source_file}]\n{doc.page_content}")
            
        context = "\n\n".join(context_parts)
        print(
            "[rag] "
            f"query='{retrieval_query[:160]}' "
            f"sources={sorted(source_names)}"
        )

        farm_context = get_farm_context(request.get("user_id"), analysis_query)
        print(
            "[api/chat] "
            f"user={mask_user_id(request.get('user_id'))} "
            f"farm_context_chars={len(farm_context)}"
        )
        prompt_parts = []
        if farm_context:
            prompt_parts.append(f"Ngữ cảnh vườn từ app:\n{farm_context}")

        prompt_parts.append(f"Tài liệu tham khảo:\n{context}")
        prompt_parts.append(f"Câu hỏi của người dùng: {request['question']}")
        prompt = "\n\n".join(prompt_parts)
        
        # 3. Tạo lịch sử tin nhắn
        messages = [SystemMessage(content=system_template)]
        for msg in request["history"]:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
                
        messages.append(HumanMessage(content=prompt))
        
        # 4. Trả lời
        response = selected_llm.invoke(messages)
        follow_up_questions = extract_follow_up_questions(response.content)
        follow_up_options = build_follow_up_options(follow_up_questions)
        answer = finalize_answer(
            response.content,
            source_names,
            follow_up_questions,
            request["question"],
        )
        
        disease_images_data = fetch_disease_images(request["question"], answer)
        disease_images = [
            DiseaseImage(name=item["name"], imageUrl=item["imageUrl"])
            for item in disease_images_data
        ]
        
        return ChatResponse(
            answer=answer,
            sources=list(source_names),
            needs_follow_up=bool(follow_up_questions),
            follow_up_questions=follow_up_questions,
            follow_up_options=follow_up_options,
            images=disease_images,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/debug/farm-context", response_model=FarmContextDebugResponse, dependencies=[Depends(verify_security)])
async def farm_context_debug(userId: str = Query(..., min_length=1)):
    if os.getenv("FARM_CONTEXT_DEBUG", "").lower() not in {"1", "true", "yes", "on"}:
        raise HTTPException(
            status_code=404,
            detail="Debug endpoint is disabled. Set FARM_CONTEXT_DEBUG=true to enable it locally.",
        )

    try:
        db = get_firestore_client()
        if db is None:
            return FarmContextDebugResponse(
                enabled=True,
                user=mask_user_id(userId),
                firebase_connected=False,
                farmAddress_docs=0,
                diary_entries=0,
                context_chars=0,
            )

        address_records, diary_records = fetch_farm_records(userId)
        context = format_farm_context(address_records, diary_records)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Khong doc duoc Firestore: {exc}")

    return FarmContextDebugResponse(
        enabled=True,
        user=mask_user_id(userId),
        firebase_connected=True,
        farmAddress_docs=len(address_records),
        diary_entries=len(diary_records),
        context_chars=len(context),
    )
