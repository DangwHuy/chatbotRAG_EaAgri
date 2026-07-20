import os
import glob
import re
import unicodedata
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ModuleNotFoundError:
    firebase_admin = None
    credentials = None
    firestore = None


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DEFAULT_DIARY_LIMIT = int(os.getenv("FARM_DIARY_LIMIT", "24"))
DIARY_CONTEXT_LIMIT = int(os.getenv("FARM_DIARY_CONTEXT_LIMIT", "8"))
MAX_CONTEXT_CHARS = int(os.getenv("FARM_CONTEXT_MAX_CHARS", "4200"))

_firestore_client = None
_firestore_error_logged = False


FIELD_LABELS = {
    "address": "Địa chỉ",
    "addressLine": "Địa chỉ",
    "category": "Hoạt động",
    "createdAt": "Tạo lúc",
    "crop": "Cây trồng",
    "date": "Ngày",
    "description": "Mô tả",
    "detail": "Chi tiết",
    "district": "Huyện",
    "dose": "Liều lượng",
    "dosage": "Liều lượng",
    "extra1": "Chi tiết 1",
    "extra2": "Chi tiết 2",
    "farmName": "Tên vườn",
    "fertilizer": "Phân bón",
    "lat": "Vĩ độ",
    "latitude": "Vĩ độ",
    "lng": "Kinh độ",
    "longitude": "Kinh độ",
    "note": "Ghi chú",
    "notes": "Ghi chú",
    "pest": "Sâu hại",
    "plot": "Lô",
    "province": "Tỉnh",
    "quantity": "Số lượng",
    "title": "Tiêu đề",
    "updatedAt": "Cập nhật lúc",
    "village": "Thôn/buôn",
    "ward": "Xã/phường",
    "weather": "Thời tiết",
}

ADDRESS_PRIORITY = [
    "farmName",
    "address",
    "addressLine",
    "village",
    "ward",
    "district",
    "province",
    "latitude",
    "longitude",
    "lat",
    "lng",
]

DIARY_PRIORITY = [
    "date",
    "category",
    "crop",
    "plot",
    "title",
    "description",
    "detail",
    "note",
    "notes",
    "fertilizer",
    "dose",
    "dosage",
    "quantity",
    "extra1",
    "extra2",
    "weather",
    "pest",
    "createdAt",
]

STOPWORDS = {
    "ai",
    "anh",
    "ba",
    "ban",
    "bi",
    "cac",
    "cach",
    "cai",
    "can",
    "cho",
    "cua",
    "da",
    "dang",
    "day",
    "de",
    "di",
    "duoc",
    "gan",
    "gi",
    "hay",
    "hoi",
    "la",
    "lam",
    "minh",
    "nay",
    "nen",
    "nhu",
    "nhung",
    "noi",
    "o",
    "phai",
    "sao",
    "toi",
    "trong",
    "tu",
    "va",
    "ve",
    "voi",
    "vuon",
}

DISEASE_QUESTION_KEYWORDS = {
    "benh",
    "bong",
    "chay",
    "chet",
    "dom",
    "heo",
    "kho",
    "nam",
    "nut",
    "rang",
    "rep",
    "rung",
    "sau",
    "soc",
    "thoi",
    "thuoc",
    "vang",
    "xi",
    "xu",
}

RECENT_ACTIVITY_KEYWORDS = {
    "gan",
    "hoat",
    "ky",
    "lam",
    "moi",
    "nhat",
    "nhatky",
}

RISK_ACTIVITY_KEYWORDS = {
    "bon",
    "cat",
    "lieu",
    "mua",
    "ngap",
    "npk",
    "nuoc",
    "phan",
    "phun",
    "sat",
    "thuoc",
    "tia",
    "tuoi",
    "ure",
}

RISK_CATEGORIES = {
    "bon phan",
    "phun thuoc",
    "tuoi nuoc",
    "quan sat",
    "cat tia",
}


def _log_firestore_error(message: str) -> None:
    global _firestore_error_logged
    if not _firestore_error_logged:
        print(message)
        _firestore_error_logged = True


def mask_user_id(user_id: Optional[str]) -> str:
    user_id = (user_id or "").strip()
    if not user_id:
        return "<missing>"
    if len(user_id) <= 8:
        return user_id[0] + "***" + user_id[-1]
    return user_id[:4] + "..." + user_id[-4:]


def _resolve_existing_path(raw_path: str) -> Optional[str]:
    if not raw_path:
        return None

    candidates = []
    if os.path.isabs(raw_path):
        candidates.append(raw_path)
    else:
        candidates.extend(
            [
                os.path.abspath(raw_path),
                os.path.join(BASE_DIR, raw_path),
                os.path.join(PROJECT_ROOT, raw_path),
            ]
        )

    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return None


def _service_account_path() -> Optional[str]:
    configured_path = (
        os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
        or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        or ""
    )
    resolved_path = _resolve_existing_path(configured_path)
    if resolved_path:
        return resolved_path

    for filename in ("serviceAccountKey.json", "firebase-service-account.json"):
        resolved_path = _resolve_existing_path(filename)
        if resolved_path:
            return resolved_path

    for folder in (BASE_DIR, PROJECT_ROOT):
        matches = sorted(glob.glob(os.path.join(folder, "*firebase-adminsdk*.json")))
        if matches:
            return matches[0]

    return None


def get_firestore_client():
    global _firestore_client

    if _firestore_client is not None:
        return _firestore_client

    if firebase_admin is None:
        _log_firestore_error(
            "[farm_context] Chua cai firebase-admin, bo qua ngu canh nhat ky nong ho."
        )
        return None

    try:
        try:
            firebase_admin.get_app()
        except ValueError:
            service_account_path = _service_account_path()
            if service_account_path:
                cred = credentials.Certificate(service_account_path)
                firebase_admin.initialize_app(cred)
            else:
                firebase_admin.initialize_app()

        _firestore_client = firestore.client()
        return _firestore_client
    except Exception as exc:
        _log_firestore_error(f"[farm_context] Khong khoi tao duoc Firestore: {exc}")
        return None


def _format_key(key: str) -> str:
    if key in FIELD_LABELS:
        return FIELD_LABELS[key]

    words = []
    current = ""
    for char in key:
        if char.isupper() and current:
            words.append(current)
            current = char.lower()
        elif char in {"_", "-"}:
            if current:
                words.append(current)
                current = ""
        else:
            current += char
    if current:
        words.append(current)

    return " ".join(words).capitalize() if words else key


def _format_value(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M")

    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")

    if hasattr(value, "latitude") and hasattr(value, "longitude"):
        return f"{value.latitude}, {value.longitude}"

    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            item_text = _format_value(item)
            if item_text:
                parts.append(f"{_format_key(str(key))}: {item_text}")
        return "; ".join(parts)

    if isinstance(value, (list, tuple, set)):
        parts = [_format_value(item) for item in value]
        return ", ".join(part for part in parts if part)

    return str(value).strip()


def _normalize_search_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    no_accents = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9\s]", " ", no_accents)


def _tokens(text: str) -> List[str]:
    normalized = _normalize_search_text(text)
    return [token for token in normalized.split() if len(token) > 1 and token not in STOPWORDS]


def _question_intent(question: Optional[str]) -> str:
    question_tokens = set(_tokens(question or ""))
    if question_tokens & DISEASE_QUESTION_KEYWORDS:
        return "diagnosis"
    if {"hoat", "dong"} <= question_tokens or question_tokens & RECENT_ACTIVITY_KEYWORDS:
        return "recent_activity"
    return "general"


def _record_text(data: Dict[str, Any]) -> str:
    return _normalize_search_text(_format_document(data, DIARY_PRIORITY))


def _category_text(data: Dict[str, Any]) -> str:
    return _normalize_search_text(_format_value(data.get("category")))


def _score_diary_record(
    data: Dict[str, Any],
    question_tokens: set,
    intent: str,
    index: int,
) -> int:
    text = _record_text(data)
    record_tokens = set(text.split())
    category = _category_text(data)

    score = max(0, 5 - index)
    score += len(question_tokens & record_tokens) * 4

    if intent == "diagnosis":
        if category in RISK_CATEGORIES:
            score += 8
        if record_tokens & RISK_ACTIVITY_KEYWORDS:
            score += 5
        if record_tokens & DISEASE_QUESTION_KEYWORDS:
            score += 4
    elif intent == "recent_activity":
        score += max(0, 8 - index)

    return score


def select_relevant_diary_records(
    diary_records: List[Tuple[str, Dict[str, Any]]],
    question: Optional[str],
    limit: int = DIARY_CONTEXT_LIMIT,
) -> Tuple[str, List[Tuple[str, Dict[str, Any]]]]:
    if not diary_records:
        return "Không có nhật ký để lọc.", []

    intent = _question_intent(question)
    if intent == "recent_activity":
        return (
            "Người dùng hỏi tổng quan hoạt động gần đây, lấy các hoạt động mới nhất.",
            diary_records[: min(5, limit)],
        )

    question_tokens = set(_tokens(question or ""))
    ranked_records = []
    for index, (doc_id, data) in enumerate(diary_records):
        score = _score_diary_record(data, question_tokens, intent, index)
        ranked_records.append((score, index, doc_id, data))

    ranked_records.sort(key=lambda item: (-item[0], item[1]))
    selected = [(doc_id, data) for _, _, doc_id, data in ranked_records[:limit]]

    if intent == "diagnosis":
        reason = (
            "Người dùng hỏi bệnh/triệu chứng, đã ưu tiên nhật ký bón phân, phun thuốc, "
            "tưới nước, quan sát và các ghi chú trùng dấu hiệu."
        )
    else:
        reason = "Đã chọn các nhật ký gần đây và có từ khóa gần nhất với câu hỏi."

    return reason, selected


def _ordered_items(data: Dict[str, Any], priority: List[str]) -> List[Tuple[str, Any]]:
    items = []
    used_keys = set()

    for key in priority:
        if key in data:
            items.append((key, data[key]))
            used_keys.add(key)

    for key, value in data.items():
        if key not in used_keys:
            items.append((key, value))

    return items


def _format_document(data: Dict[str, Any], priority: List[str]) -> str:
    fields = []
    for key, value in _ordered_items(data, priority):
        value_text = _format_value(value)
        if value_text:
            fields.append(f"{_format_key(str(key))}: {value_text}")

    return "; ".join(fields)


def _stream_to_dicts(docs: Iterable[Any]) -> List[Tuple[str, Dict[str, Any]]]:
    records = []
    for doc in docs:
        data = doc.to_dict() or {}
        records.append((doc.id, data))
    return records


def fetch_farm_records(user_id: str, diary_limit: int = DEFAULT_DIARY_LIMIT) -> Tuple[List[Tuple[str, Dict[str, Any]]], List[Tuple[str, Dict[str, Any]]]]:
    db = get_firestore_client()
    if db is None:
        return [], []

    address_docs = (
        db.collection("users")
        .document(user_id)
        .collection("farmAddress")
        .stream()
    )
    diary_docs = (
        db.collection("farm_diary")
        .document(user_id)
        .collection("entries")
        .order_by("date", direction=firestore.Query.DESCENDING)
        .limit(diary_limit)
        .stream()
    )

    return _stream_to_dicts(address_docs), _stream_to_dicts(diary_docs)


def format_farm_context(
    address_records: List[Tuple[str, Dict[str, Any]]],
    diary_records: List[Tuple[str, Dict[str, Any]]],
    question: Optional[str] = None,
    diary_context_limit: int = DIARY_CONTEXT_LIMIT,
) -> str:
    sections = []

    if address_records:
        address_lines = []
        for doc_id, data in address_records:
            text = _format_document(data, ADDRESS_PRIORITY)
            if text:
                address_lines.append(f"- {doc_id}: {text}")
        if address_lines:
            sections.append("Địa chỉ vườn:\n" + "\n".join(address_lines))

    if diary_records:
        selection_reason, selected_diary_records = select_relevant_diary_records(
            diary_records,
            question,
            diary_context_limit,
        )
        diary_lines = []
        for index, (doc_id, data) in enumerate(selected_diary_records, start=1):
            text = _format_document(data, DIARY_PRIORITY)
            if text:
                diary_lines.append(f"- #{index} ({doc_id}): {text}")
        if diary_lines:
            sections.append(
                "Nhật ký nông hộ liên quan đến câu hỏi:\n"
                f"Cách chọn: {selection_reason}\n"
                + "\n".join(diary_lines)
            )

    return "\n\n".join(sections)


def get_farm_context(
    user_id: Optional[str],
    question: Optional[str] = None,
    diary_limit: int = DEFAULT_DIARY_LIMIT,
) -> str:
    user_id = (user_id or "").strip()
    if not user_id:
        print("[farm_context] Khong co userId trong request chat, bo qua nhat ky nong ho.")
        return ""

    try:
        address_records, diary_records = fetch_farm_records(user_id, diary_limit)
        context = format_farm_context(address_records, diary_records, question)
    except Exception as exc:
        print(f"[farm_context] Khong lay duoc ngu canh nong ho: {exc}")
        return ""

    print(
        "[farm_context] "
        f"user={mask_user_id(user_id)} "
        f"farmAddress_docs={len(address_records)} "
        f"diary_entries={len(diary_records)} "
        f"context_chars={len(context)}"
    )

    if len(context) > MAX_CONTEXT_CHARS:
        return context[:MAX_CONTEXT_CHARS].rstrip() + "\n... (đã rút gọn nhật ký do quá dài)"

    return context
