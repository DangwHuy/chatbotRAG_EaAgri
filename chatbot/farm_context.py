import os
import glob
import re
import time
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

PEST_DISEASES_CACHE_TTL = int(os.getenv("PEST_DISEASES_CACHE_TTL", "300"))

_firestore_client = None
_firestore_error_logged = False
_pest_diseases_cache: List[Tuple[str, Dict[str, Any]]] = []
_pest_diseases_cache_ts: float = 0.0


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
    "name": "Tên vườn",
    "area": "Diện tích (ha)",
    "certifications": "Chứng nhận",
}

ADDRESS_PRIORITY = [
    "name",
    "farmName",
    "area",
    "certifications",
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
    "farmName",
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
    lowered = (text or "").lower().replace("đ", "d")
    decomposed = unicodedata.normalize("NFD", lowered)
    no_accents = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    cleaned = re.sub(r"[^a-z0-9\s]", " ", no_accents)
    return re.sub(r"\s+", " ", cleaned).strip()


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
    from firebase_admin.firestore import Query
    db = get_firestore_client()
    if db is None:
        return [], []

    # 1. Lấy danh sách vườn từ collection farms
    farm_mapping = {}
    farms_list = []
    try:
        farms_docs = db.collection("farms").where("ownerId", "==", user_id).stream()
        for f in farms_docs:
            f_data = f.to_dict() or {}
            f_name = f_data.get("name", f"Vườn {f.id[-4:]}")
            farm_mapping[f.id] = f_name
            farms_list.append((f.id, f_data))
    except Exception as e:
        print(f"Lỗi khi lấy thông tin farms: {e}")

    diary_docs = (
        db.collection("farm_diary")
        .document(user_id)
        .collection("entries")
        .order_by("date", direction=Query.DESCENDING)
        .limit(diary_limit)
        .stream()
    )

    diary_records = []
    for doc in diary_docs:
        data = doc.to_dict() or {}
        # Gắn tên vườn vào dữ liệu
        farm_id = data.get("traceabilityFarmId")
        if farm_id and farm_id in farm_mapping:
            data["farmName"] = f"[{farm_mapping[farm_id]}]"
        elif farm_id:
            data["farmName"] = f"[Vườn {farm_id[-4:]}]"
        else:
            data["farmName"] = "[Vườn Mặc Định]"
        diary_records.append((doc.id, data))

    return farms_list, diary_records


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


GENERIC_DISEASE_TAGS = {
    "benh", "benh la", "benh re", "benh cay", "benh sau rieng",
    "nam", "nam benh", "nam dot", "nam trai", "con trung", "dich hai",
    "sau rieng", "cay sau rieng", "ca phe", "cay ca phe", "ho tieu", "tieu", "bo",
    "la", "la non", "la gia", "la sau rieng", "dot", "dot non", "choi", "choi non",
    "than", "canh", "canh non", "re", "re non", "re to", "re sau rieng", "goc", "co re",
    "hoa", "bong", "hoa sau rieng", "trai", "qua", "trai non", "cuong", "cuong trai", "vo trai",
    "cay con", "chet cay", "mua mua", "mua kho", "mua lon", "do am cao", "dat yem khi",
    "chich hut", "kien", "mat ngot",
}

BROAD_SYMPTOM_TAGS = {
    "vang la", "la vang", "chay la", "rung la", "rung trai", "rung hoa",
    "dom nau", "dom vang", "heo la", "heo canh", "heo cay", "cay heo",
    "kho canh", "kho dot", "kho ngon", "kho bong", "chet ngon", "chet dot",
    "thoi re", "thoi than", "thoi goc", "thoi trai", "lo duc", "ri nhua",
    "chay nhua", "nghet re", "thieu oxy", "re den", "re nau", "suy re",
    "mun go", "phan sau", "khuyet la", "thung la", "can la", "hai re",
    "xoan la", "seo trai", "quang vang", "giam dau trai", "hoa nau den",
    "co re nau den", "not sung re", "lop bot trang", "lop sap trang", "bui than",
    "sau non", "ung nuoc", "ngap ung",
}

SCIENTIFIC_LATIN_TERMS = {
    "cephaleuros", "colletotrichum", "phytophthora", "fusarium", "rhizoctonia",
    "phomopsis", "erythricium", "xyleborus", "psyllid", "thrips", "nematode",
    "pythium", "lasiodiplodia", "cercospora",
}

KNOWN_CROP_ALIASES = {
    "sau rieng": ["sau rieng"],
    "ca phe": ["ca phe", "coffee"],
    "ho tieu": ["ho tieu", "cay tieu", "hat tieu"],
    "bo": ["cay bo", "qua bo", "trai bo"],
    "mac ca": ["mac ca", "macca"],
    "cao su": ["cao su"],
    "dieu": ["cay dieu", "hat dieu"],
}


def _normalize_accented_text(text: str) -> str:
    lowered = (text or "").lower()
    cleaned = re.sub(r"[^\w\sà-ỹ]", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def _extract_image_url(data: Dict[str, Any]) -> str:
    for key in ("imageUrl", "image", "thumbnailUrl"):
        val = (data.get(key) or "").strip() if isinstance(data.get(key), str) else ""
        if val.startswith("http"):
            return val
    for list_key in ("imageUrls", "images"):
        items = data.get(list_key)
        if isinstance(items, list):
            for item in items:
                if isinstance(item, str) and item.strip().startswith("http"):
                    return item.strip()
                if isinstance(item, dict):
                    u = (item.get("url") or item.get("imageUrl") or "").strip()
                    if u.startswith("http"):
                        return u
    return ""


def _get_pest_diseases_records() -> List[Tuple[str, Dict[str, Any]]]:
    global _pest_diseases_cache, _pest_diseases_cache_ts
    now = time.time()
    if _pest_diseases_cache and (now - _pest_diseases_cache_ts) < PEST_DISEASES_CACHE_TTL:
        return _pest_diseases_cache

    db = get_firestore_client()
    if db is None:
        return _pest_diseases_cache

    try:
        records: List[Tuple[str, Dict[str, Any]]] = []
        for doc in db.collection("pest_diseases").stream():
            data = doc.to_dict() or {}
            if data.get("isActive") is False:
                continue
            records.append((doc.id, data))
        _pest_diseases_cache = records
        _pest_diseases_cache_ts = now
        return records
    except Exception as exc:
        print(f"[farm_context] Lỗi tải cache pest_diseases: {exc}")
        return _pest_diseases_cache


def _detect_mentioned_crops(text: str) -> set:
    norm_pad = f" {_normalize_search_text(text)} "
    found = set()
    for canonical_crop, aliases in KNOWN_CROP_ALIASES.items():
        if any(f" {alias} " in norm_pad for alias in aliases):
            found.add(canonical_crop)
    return found


def _extract_core_disease_phrases(name: str) -> List[Tuple[str, str]]:
    if not name:
        return []
    raw_parts = [p.strip() for p in re.split(r"[,;()/]+", name) if p.strip()]
    raw_parts.insert(0, re.sub(r"\([^)]*\)", " ", name).strip())

    variants: List[Tuple[str, str]] = []
    seen_norm = set()

    strip_prefixes_acc = ("bệnh nấm ", "bệnh ", "côn trùng ")
    strip_suffixes_acc = (
        " hại rễ sầu riêng",
        " hại sầu riêng",
        " trên sầu riêng",
        " sầu riêng",
        " hại cà phê",
        " cà phê",
        " hồ tiêu",
    )

    for part in raw_parts:
        acc = _normalize_accented_text(part)
        if not acc:
            continue

        candidates_acc = [acc]
        trimmed = acc
        for pref in strip_prefixes_acc:
            if trimmed.startswith(pref):
                trimmed = trimmed[len(pref):].strip()
        for suff in strip_suffixes_acc:
            if trimmed.endswith(suff):
                trimmed = trimmed[:-len(suff)].strip()
        if trimmed and trimmed != acc:
            candidates_acc.append(trimmed)

        for cand_acc in candidates_acc:
            cand_norm = _normalize_search_text(cand_acc)
            if not cand_norm or cand_norm in GENERIC_DISEASE_TAGS or cand_norm in seen_norm:
                continue
            if len(cand_norm.split()) >= 2 or len(cand_norm) >= 5:
                seen_norm.add(cand_norm)
                variants.append((cand_acc, cand_norm))

    return variants


def is_image_request(question: str) -> bool:
    norm = _normalize_search_text(question)
    if not norm:
        return False
    padded = f" {norm} "
    image_phrases = (
        " hinh anh ",
        " xem anh ",
        " cho anh ",
        " xin anh ",
        " xem hinh ",
        " cho hinh ",
        " anh benh ",
        " hinh benh ",
        " anh thuc te ",
        " hinh thuc te ",
        " co anh ",
        " co hinh ",
        " gui anh ",
        " gui hinh ",
        " anh sau ",
        " anh nam ",
    )
    if any(phrase in padded for phrase in image_phrases):
        return True
    words = norm.split()
    if len(words) >= 2 and words[0] in {"anh", "hinh"}:
        return True
    return False


def _has_anaphora_disease_ref(question: str) -> bool:
    padded = f" {_normalize_search_text(question)} "
    refs = (" benh do ", " benh nay ", " con do ", " sau do ", " loai nay ", " loai do ", " cua no ")
    return any(r in padded for r in refs) or _normalize_search_text(question) in {
        "cho xem anh", "cho xem hinh", "co anh khong", "co hinh anh khong", "hinh anh", "xem anh"
    }


def search_pest_diseases(
    question: str,
    answer: str = "",
    history_text: str = "",
    limit: int = 3,
    min_score: int = 60,
) -> List[Dict[str, Any]]:
    records = _get_pest_diseases_records()
    if not records:
        return []

    q_norm = _normalize_search_text(question)
    a_norm = _normalize_search_text(answer)
    q_acc = _normalize_accented_text(question)
    a_acc = _normalize_accented_text(answer)

    q_norm_pad = f" {q_norm} " if q_norm else ""
    a_norm_pad = f" {a_norm} " if a_norm else ""
    q_acc_pad = f" {q_acc} " if q_acc else ""
    a_acc_pad = f" {a_acc} " if a_acc else ""

    # Xác định loại cây trồng đang được nhắc tới (nếu có)
    mentioned_crops = _detect_mentioned_crops(question)
    if not mentioned_crops and (history_text or answer):
        mentioned_crops = _detect_mentioned_crops(f"{history_text} {answer}")

    # BƯỚC 1: Tìm tất cả cụm tên bệnh cốt lõi khớp trong question / answer để khử trùng lặp cụm con (vd: "đốm lá" nằm trong "đốm lá mắt cua")
    all_q_matched_cores: set = set()
    all_a_matched_cores: set = set()
    doc_prepared = []

    for doc_id, data in records:
        name = (data.get("name") or "").strip()
        raw_crops = data.get("crops") or []
        if isinstance(raw_crops, str):
            raw_crops = [raw_crops]
        doc_crops_norm = {_normalize_search_text(str(c)) for c in raw_crops if str(c).strip()}

        if doc_crops_norm and mentioned_crops and not (doc_crops_norm & mentioned_crops):
            continue

        core_phrases = _extract_core_disease_phrases(name)
        for _, c_norm in core_phrases:
            if q_norm_pad and f" {c_norm} " in q_norm_pad:
                all_q_matched_cores.add(c_norm)
            if a_norm_pad and f" {c_norm} " in a_norm_pad:
                all_a_matched_cores.add(c_norm)

        doc_prepared.append((doc_id, data, name, doc_crops_norm, core_phrases))

    def _is_strictly_subsumed(phrase: str, matched_set: set, padded_text: str) -> bool:
        longer = [m for m in matched_set if m != phrase and f" {phrase} " in f" {m} "]
        if not longer:
            return False
        scrubbed = padded_text
        for lg in sorted(longer, key=len, reverse=True):
            scrubbed = scrubbed.replace(f" {lg} ", " ")
        return f" {phrase} " not in scrubbed

    scored_results: List[Dict[str, Any]] = []

    for doc_id, data, name, doc_crops_norm, core_phrases in doc_prepared:
        score = 0

        # 1. Chấm điểm khớp Tên bệnh cốt lõi
        best_q_core = 0
        best_a_core = 0
        for c_acc, c_norm in core_phrases:
            w_count = len(c_norm.split())
            if q_norm_pad and f" {c_norm} " in q_norm_pad:
                if not _is_strictly_subsumed(c_norm, all_q_matched_cores, q_norm_pad):
                    pts = 150 + w_count * 15 + (15 if f" {c_acc} " in q_acc_pad else 0)
                    best_q_core = max(best_q_core, pts)
            elif a_norm_pad and f" {c_norm} " in a_norm_pad:
                if not _is_strictly_subsumed(c_norm, all_a_matched_cores, a_norm_pad):
                    pts = 85 + w_count * 10 + (10 if f" {c_acc} " in a_acc_pad else 0)
                    best_a_core = max(best_a_core, pts)

        score += best_q_core + best_a_core

        # 2. Chấm điểm Tags (tách biệt Tag định danh đặc hiệu và Tag triệu chứng rộng)
        raw_tags = data.get("tags") or []
        if isinstance(raw_tags, str):
            raw_tags = [raw_tags]

        best_specific_tag = 0
        broad_symptom_pts = 0

        for raw_t in raw_tags:
            t_acc = _normalize_accented_text(str(raw_t))
            t_norm = _normalize_search_text(str(raw_t))
            if not t_norm or t_norm in GENERIC_DISEASE_TAGS or t_norm in doc_crops_norm:
                continue

            words = t_norm.split()
            if len(words) == 1:
                if t_norm in SCIENTIFIC_LATIN_TERMS or (t_norm.isascii() and len(t_norm) >= 6 and t_acc == t_norm):
                    if q_norm_pad and f" {t_norm} " in q_norm_pad:
                        best_specific_tag = max(best_specific_tag, 115)
                    elif a_norm_pad and f" {t_norm} " in a_norm_pad:
                        best_specific_tag = max(best_specific_tag, 65)
                else:
                    # Từ đơn tiếng Việt (vd: "tảo", "rong") chỉ khớp khi gõ đúng dấu để tránh nhầm "tạo", "rộng"
                    if len(t_acc) >= 3:
                        if q_acc_pad and f" {t_acc} " in q_acc_pad:
                            best_specific_tag = max(best_specific_tag, 55)
                        elif a_acc_pad and f" {t_acc} " in a_acc_pad:
                            best_specific_tag = max(best_specific_tag, 25)
            else:
                if t_norm in BROAD_SYMPTOM_TAGS:
                    if q_norm_pad and f" {t_norm} " in q_norm_pad:
                        broad_symptom_pts += 22
                    elif a_norm_pad and f" {t_norm} " in a_norm_pad:
                        broad_symptom_pts += 8
                else:
                    if q_norm_pad and f" {t_norm} " in q_norm_pad:
                        if not _is_strictly_subsumed(t_norm, all_q_matched_cores, q_norm_pad):
                            pts = 110 + len(words) * 10 + (10 if f" {t_acc} " in q_acc_pad else 0)
                            best_specific_tag = max(best_specific_tag, pts)
                    elif a_norm_pad and f" {t_norm} " in a_norm_pad:
                        if not _is_strictly_subsumed(t_norm, all_a_matched_cores, a_norm_pad):
                            pts = 60 + len(words) * 5 + (5 if f" {t_acc} " in a_acc_pad else 0)
                            best_specific_tag = max(best_specific_tag, pts)

        # Nếu đã khớp Core Name thì Tag đặc hiệu chỉ cộng thưởng nhỏ; nếu chưa khớp Core Name thì dùng điểm Tag đặc hiệu
        if best_q_core > 0 or best_a_core > 0:
            score += min(25, best_specific_tag // 5)
        else:
            score += best_specific_tag

        score += min(55, broad_symptom_pts)

        # Ưu tiên nhẹ cây Sầu riêng khi người dùng không chỉ định loại cây
        if score > 0 and not mentioned_crops and "sau rieng" in doc_crops_norm:
            score += 5

        if score >= min_score:
            scored_results.append({
                "id": doc_id,
                "score": score,
                "name": name or "Hình ảnh sâu bệnh",
                "imageUrl": _extract_image_url(data),
                "data": data,
            })

    if not scored_results:
        return []

    scored_results.sort(key=lambda item: -item["score"])
    top_score = scored_results[0]["score"]
    cutoff = max(min_score, int(top_score * 0.72)) if min_score >= 60 else min_score

    return [item for item in scored_results if item["score"] >= cutoff][:limit]


def _format_pest_disease_card(item: Dict[str, Any]) -> str:
    data = item["data"]
    name = item["name"]
    crops = _format_value(data.get("crops")) or "Sầu riêng"
    emergency = _format_value(data.get("emergency_level"))
    parts = _format_value(data.get("affected_parts"))
    season = _format_value(data.get("season"))

    meta_bits = [f"Cây: {crops}"]
    if emergency:
        meta_bits.append(f"Nguy hại: {emergency}")
    if parts:
        meta_bits.append(f"Bộ phận: {parts}")
    if season:
        meta_bits.append(f"Mùa: {season}")

    lines = [f"- {name} ({' | '.join(meta_bits)})"]

    def _join_bullets(raw_val: Any, max_items: int) -> str:
        items = [raw_val] if isinstance(raw_val, str) else (raw_val or [])
        cleaned = [str(x).strip().rstrip(".;,") for x in items[:max_items] if str(x).strip()]
        return "; ".join(cleaned)

    sym_text = _join_bullets(data.get("symptoms"), 4)
    if sym_text:
        lines.append(f"  + Triệu chứng chuẩn: {sym_text}.")

    trt_text = _join_bullets(data.get("treatment"), 4)
    if trt_text:
        lines.append(f"  + Xử lý chuẩn: {trt_text}.")

    prv_text = _join_bullets(data.get("prevention"), 2)
    if prv_text:
        lines.append(f"  + Phòng ngừa: {prv_text}.")

    return "\n".join(lines)


def build_pest_disease_prompt_context(
    question: str,
    history_text: str = "",
) -> Tuple[str, List[Dict[str, str]], bool]:
    """
    Tra cứu kho pest_diseases TRƯỚC khi gọi LLM để:
    1. Cung cấp kiến thức triệu chứng/điều trị chuẩn từ Firestore cho AI.
    2. Báo rõ cho AI biết ảnh bệnh nào ĐÃ ĐƯỢC ĐÍNH KÈM bên dưới tin nhắn (tránh AI tự chối không hiển thị được ảnh).
    """
    img_req = is_image_request(question)

    strong_matches = search_pest_diseases(question=question, history_text=history_text, limit=3, min_score=60)
    if not strong_matches and history_text and (img_req or _has_anaphora_disease_ref(question)):
        strong_matches = search_pest_diseases(question=history_text, limit=2, min_score=70)

    pre_images: List[Dict[str, str]] = []
    seen_urls = set()
    for item in strong_matches:
        url = item["imageUrl"]
        if url and url not in seen_urls:
            seen_urls.add(url)
            pre_images.append({"name": item["name"], "imageUrl": url})

    knowledge_matches = strong_matches
    if not knowledge_matches:
        knowledge_matches = search_pest_diseases(question=question, history_text=history_text, limit=2, min_score=22)

    sections: List[str] = []
    if knowledge_matches:
        cards = [_format_pest_disease_card(item) for item in knowledge_matches[:2]]
        sections.append("Dữ liệu từ Kho Sâu Bệnh của Ea Agri (ưu tiên đối chiếu):\n" + "\n".join(cards))

    if pre_images:
        attached_names = ", ".join(f"[{img['name']}]" for img in pre_images)
        sections.append(
            f"[TRẠNG THÁI HÌNH ẢNH]: Hệ thống ĐÃ TỰ ĐỘNG ĐÍNH KÈM {len(pre_images)} hình ảnh thực tế "
            f"({attached_names}) hiển thị ngay bên dưới câu trả lời này trên màn hình ứng dụng. "
            "TUYỆT ĐỐI KHÔNG nói 'không thể hiển thị hình ảnh'; hãy chủ động mời bà con quan sát hình ảnh bên dưới "
            "và chỉ rõ các đặc điểm nhận diện chính trên ảnh!"
        )
    elif img_req:
        sections.append(
            "[TRẠNG THÁI HÌNH ẢNH]: Người dùng đang yêu cầu xem hình ảnh, nhưng hiện Kho hình ảnh của Ea Agri "
            "chưa có ảnh chụp khớp trực tiếp với tên bệnh trong câu hỏi. TUYỆT ĐỐI KHÔNG nói máy móc 'AI không thể hiển thị hình ảnh'; "
            "hãy báo lịch sự 'Hiện kho hình ảnh của Ea Agri chưa cập nhật ảnh chụp thực tế cho bệnh này' rồi mô tả ngắn gọn dấu hiệu nhận diện bằng mắt thường."
        )

    return "\n\n".join(sections), pre_images, img_req


def fetch_disease_images(
    question: str,
    answer: str = "",
    history_text: str = "",
) -> List[Dict[str, str]]:
    """
    Truy vấn kho 'pest_diseases' (có cache RAM + hỗ trợ không dấu) để lấy hình ảnh bệnh minh họa
    khớp chính xác với bệnh trong câu hỏi hoặc chẩn đoán của AI.
    """
    try:
        matches = search_pest_diseases(
            question=question,
            answer=answer,
            history_text=history_text,
            limit=3,
            min_score=60,
        )
        if not matches and history_text and (is_image_request(question) or _has_anaphora_disease_ref(question)):
            matches = search_pest_diseases(question=history_text, limit=2, min_score=70)

        matched_images: List[Dict[str, str]] = []
        seen_urls = set()
        for item in matches:
            image_url = item["imageUrl"]
            if image_url and image_url not in seen_urls:
                seen_urls.add(image_url)
                matched_images.append({
                    "name": item["name"],
                    "imageUrl": image_url,
                })
                if len(matched_images) >= 3:
                    break

        return matched_images
    except Exception as exc:
        print(f"[farm_context] Lỗi khi truy vấn pest_diseases: {exc}")
        return []


