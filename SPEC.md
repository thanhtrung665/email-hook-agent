# SPEC – Kế hoạch làm việc

> Mỗi khi có task mới: thêm một mục ở dưới (mới nhất lên đầu) gồm mục tiêu, các bước, tiêu chí hoàn thành.

## Task 1 – Test kết nối Supabase (`test_db.py`)
**Mục tiêu:** có script kiểm tra nhanh kết nối tới Supabase.

**Các bước**
1. Đọc cấu trúc dự án (repo mới, chỉ có README.md, chưa có `test_db`).
2. Tạo `test_db.py`: đọc `SUPABASE_URL`/`SUPABASE_KEY` từ `.env` hoặc biến môi trường, gọi REST API, có thể đọc thử 1 bảng.
3. Thêm `.env.example`, `.gitignore` (không commit khóa).
4. Chạy test với thông tin thật của người dùng.

**Hoàn thành khi:** `python test_db.py [bảng]` in `[OK]` với credentials thật.
