# SPEC – Kế hoạch làm việc

> Mỗi khi có task mới: thêm một mục ở dưới (mới nhất lên đầu) gồm mục tiêu, các bước, tiêu chí hoàn thành.

## Task 1 – Test kết nối Supabase (`app/tests/test_db.py`)
**Mục tiêu:** xác nhận `DATABASE_URL` (SQLAlchemy engine) kết nối được Supabase.

**Các bước**
1. Đọc code: `app/core/config.py`, `app/db/base.py`, `app/tests/test_db.py`.
2. Cài dependency (`sqlalchemy`, `pydantic-settings`, `psycopg[binary]`).
3. Chạy `python -m app.tests.test_db`.
4. Nếu lỗi, chẩn đoán (DNS/mạng/credentials) và ghi lại.

**Hoàn thành khi:** in "Kết nối Supabase thành công".
