"""Kiểm tra kết nối tới Supabase.

Cách dùng:
    cp .env.example .env   # điền SUPABASE_URL và SUPABASE_KEY
    python test_db.py [tên_bảng]

Không cần cài thư viện ngoài (chỉ dùng stdlib).
"""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def load_env(path=".env"):
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def request(url, key):
    req = urllib.request.Request(url, headers={"apikey": key, "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status, r.read().decode()


def main():
    load_env()
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        sys.exit("Thiếu SUPABASE_URL hoặc SUPABASE_KEY (đặt trong .env hoặc biến môi trường).")

    try:
        # 1. Kiểm tra API + key hợp lệ (PostgREST root)
        status, _ = request(f"{url}/rest/v1/", key)
        print(f"[OK] Kết nối Supabase thành công (HTTP {status})")

        # 2. Tuỳ chọn: đọc thử 1 dòng từ bảng
        if len(sys.argv) > 1:
            table = sys.argv[1]
            status, body = request(f"{url}/rest/v1/{table}?select=*&limit=1", key)
            print(f"[OK] Đọc bảng '{table}' (HTTP {status}): {json.dumps(json.loads(body), ensure_ascii=False)}")
    except urllib.error.HTTPError as e:
        sys.exit(f"[FAIL] HTTP {e.code}: {e.read().decode()[:300]}")
    except Exception as e:
        sys.exit(f"[FAIL] {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
