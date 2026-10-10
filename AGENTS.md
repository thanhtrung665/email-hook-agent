<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

---

# AGENTS — Quy tắc làm việc trong repo (PSBV Email Hook Agent)

> File này dành cho coding agent. **Không thay thế** `CLAUDE.md` — dùng song song:
> `CLAUDE.md` (tổng quan kiến trúc) → `AGENTS.md` (quy tắc hành vi khi sửa code) → `SPEC.md` (kế hoạch, đặc tả).

## 1. Đọc trước khi đụng code

1. `CLAUDE.md` — Part I, đặc biệt §2.6 (cơ chế approve-first) và §2.7 (Email Gateway).
2. `SPEC.md` — Part I: **P5** (cơ chế DUYỆT), **P6** (Inquiry), **P7** (Quotation), **P8** (Email Gateway), **G1.2** (schema), **G2** (điểm nối).
3. `PROGRESS.md` — Part I (nhật ký gần nhất, trạng thái hiện tại).

## 2. Nguyên tắc bất biến

- **HITL trước, agent sau:** agent **không bao giờ** tự gửi email cho khách/hãng. Mọi điểm gửi mail (P6 node I6, P7 node Q6) dừng chờ người duyệt.
- **AI không tự kích hoạt:** AI chỉ gợi ý nhãn (`email_labels.source=ai`). Chỉ khi người dùng **CHỌN + DUYỆT** nhãn thì `status=PROCESSING` + `assigned_agent={NHAN}_AGENT` mới được set, worker mới chạy.
- **Server quyết định số:** mọi con số nghiệp vụ (CBU, giá, tổng) do server tính lại (`src/lib/cbu/`), không tin body client.
- **Mọi node đều checkpoint** vào `agent_runs` — fail retry đúng node, không chạy lại từ đầu.

## 3. Database (Supabase `nvcanmdfdmyllvopxdst` — production dùng chung)

- **KHÔNG** `npx prisma migrate dev` (sẽ reset + mất dữ liệu).
- Merge schema = SQL tay idempotent (`IF NOT EXISTS`, `DO $$`, `ON CONFLICT DO NOTHING`), **chỉ thêm**, không `DROP`/`DELETE`/`ALTER` bảng Prisma.
- Chạy qua **Supabase Dashboard → SQL Editor**; mẫu: `scripts/g1_2_create_email_agent_schema.sql`.
- Trước mỗi lần chạy: đối chiếu `scripts/baseline_G1_before.json` (số dòng mọi bảng) và chụp baseline sau.

## 4. Thêm Agent mới theo nhãn (checklist cố định)

1. `app/scripts/seed_labels.py` — thêm entry nhãn (nếu nhãn mới), rồi chạy seed (idempotent).
2. `app/services/agents/{label}_agent.py` — multi-agent, mỗi node ghi `agent_runs` (QUEUED→RUNNING→DONE/FAILED/ESCALATED).
3. `app/services/agent_runner.py` — map `label → agent_name` ở **một chỗ duy nhất** (dict), không rải if/elif.
4. BFF `psbv-saleadmin-app/src/app/api/email-gateway/[id]/approve/route.ts` — kích hoạt từ màn DUYỆT.
5. UI: hiển thị timeline node ở `email-gateway/[id]/agent/page.tsx`.
6. Test: idempotency (gán lại không nhân đôi), retry, HITL (spy khẳng định không gọi route gửi mail).

## 5. Email Gateway (UI duy nhất của email-agent)

- Vị trí: `psbv-saleadmin-app/src/app/(dashboard)/email-gateway/` — **không** phát triển `frontend/` (đã legacy).
- BFF proxy ngược email-agent qua `EMAIL_AGENT_API_URL`, auth NextAuth phía browser (không lộ URL backend).
- Sidebar: mục "Email Gateway" trong `src/components/shared/sidebar.tsx::navLinks`, **ngay sau** "Đơn hàng RFQ", `adminOnly: false`.
- Design: shadcn/ui + Tailwind của webapp (slate/blue/indigo) — **không copy CSS demo** từ `frontend/`, chỉ tái dùng layout 70/30 và thứ tự trường.

## 6. Quy tắc thao tác an toàn

- **Không** ghi vào DB dùng chung khi chưa được người dùng cho phép rõ ràng (đã xảy ra với migration CBU 22/09).
- Backup trước mọi lần sửa dữ liệu thật; đối chiếu baseline sau.
- `npx tsc --noEmit` phải 0 lỗi; `ruff check .` + `mypy app` xanh trước khi nhận thay đổi phía Python.
- Không commit secrets (`.env`, `*.key`, `*.bot`); file `.env` đã bị commit ở lịch sử cũ — đã nhắc rotate key.
