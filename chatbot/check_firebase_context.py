import argparse
import os
import sys

from dotenv import load_dotenv

from farm_context import fetch_farm_records, format_farm_context, get_firestore_client, mask_user_id


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Kiem tra backend co doc duoc Firestore farm context hay khong."
    )
    parser.add_argument("--user-id", required=True, help="Firebase Auth UID can kiem tra")
    args = parser.parse_args()

    load_dotenv(override=True)
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

    print(f"Python: {sys.executable}")
    print(f"User: {mask_user_id(args.user_id)}")

    db = get_firestore_client()
    if db is None:
        print("Firebase: NOT_CONNECTED")
        print("Goi y: cai firebase-admin va kiem tra file service account JSON.")
        return 1

    address_records, diary_records = fetch_farm_records(args.user_id)
    context = format_farm_context(address_records, diary_records)

    print("Firebase: CONNECTED")
    print(f"farmAddress_docs: {len(address_records)}")
    print(f"diary_entries: {len(diary_records)}")
    print(f"context_chars: {len(context)}")

    if not context:
        print("Ket luan: Ket noi duoc Firebase nhung khong thay du lieu o dung path/schema.")
        return 2

    print("Ket luan: Da doc duoc du lieu nhat ky/dia chi vuon cho user nay.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
