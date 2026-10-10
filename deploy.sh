#!/usr/bin/env bash
# Deploy Email Hook Agent lên VPS Ubuntu 24.04
# Dùng: rsync .env riêng trước khi build (không push secrets qua git)
set -euo pipefail

VPS_HOST="${VPS_HOST:?}"
VPS_USER="${VPS_USER:-ubuntu}"
VPS_DIR="${VPS_DIR:-/opt/email-agent}"

echo "→ Đẩy code lên $VPS_USER@$VPS_HOST:$VPS_DIR"
rsync -az --delete \
  --exclude ".venv/" --exclude ".next/" --exclude "node_modules/" \
  --exclude "__pycache__/" --exclude ".git/" --exclude "storage/" \
  --exclude ".env" \
  --include ".env" \
  ./ "$VPS_USER@$VPS_HOST:$VPS_DIR/"

echo "→ Đồng bộ .env (không overwrite nếu đã có secrets trên VPS)"
scp -q .env "$VPS_USER@$VPS_HOST:$VPS_DIR/.env.new"
ssh "$VPS_USER@$VPS_HOST" "if [ ! -f $VPS_DIR/.env ]; then mv $VPS_DIR/.env.new $VPS_DIR/.env; else echo 'VPS đã có .env — bỏ qua .env.new (kiểm tra rồi xóa tay nếu muốn)'; fi"

echo "→ Build & restart"
ssh "$VPS_USER@$VPS_HOST" "cd $VPS_DIR && docker compose up -d --build"

echo "→ Healthcheck"
ssh "$VPS_USER@$VPS_HOST" "sleep 15 && curl -sf http://127.0.0.1:8000/ && echo ' ✓ backend OK' || (docker compose logs backend --tail 80; exit 1)"
ssh "$VPS_USER@$VPS_HOST" "docker compose ps && docker compose logs backend --tail 20"

cat <<EOF
Done. Lưu ý:
  - Webhook (Microsoft → VPS:8000) yêu cầu port công khai hoặc ngrok.
    WEBHOOK_BASE_URL trong .env phải là URL mà Microsoft với tới được.
  - Frontend gọi API từ TRÌNH DUYỆT, NEXT_PUBLIC_API_URL phải là URL
    người dùng nhìn thấy (IP/domain công khai), không phải http://backend.
EOF