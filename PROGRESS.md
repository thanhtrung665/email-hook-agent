# PROGRESS – Nhật ký công việc

## 2026-10-05 – Task 1: Test kết nối Supabase (branch main)
- Đọc code dự án (FastAPI + SQLAlchemy + Alembic, lưu file local, Microsoft Graph auth).
- Chạy `python -m app.tests.test_db`: **thất bại** – `connection is bad`.
- Nguyên nhân: host `db.<ref>.supabase.co` chỉ có IPv6, sandbox không hỗ trợ IPv6; ngoài ra proxy sandbox chặn (403) `*.supabase.co`.
- Chưa xác nhận được thông tin đăng nhập có đúng hay không.
- Lưu ý bảo mật: file `.env` (chứa khóa) đang bị commit trong repo.
- Tạo `SPEC.md`, `PROGRESS.md`.
