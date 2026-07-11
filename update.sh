#!/usr/bin/env bash
# ============================================================
#  resibot updater
#  کد را به‌روزرسانی می‌کند بدون اینکه دیتابیس/تنظیمات از بین برود.
#  اجرا:  bash /opt/resibot/update.sh
# ============================================================
set -euo pipefail

INSTALL_DIR="/opt/resibot"
SERVICE_NAME="resibot"

green() { printf "\033[32m%s\033[0m\n" "$*"; }
bold()  { printf "\033[1m%s\033[0m\n" "$*"; }
red()   { printf "\033[31m%s\033[0m\n" "$*"; }

if [[ $EUID -ne 0 ]]; then
  red "این اسکریپت باید با کاربر root اجرا شود."
  exit 1
fi

if [[ ! -d "$INSTALL_DIR/.git" ]]; then
  red "نصب پیدا نشد. ابتدا install.sh را اجرا کنید."
  exit 1
fi

cd "$INSTALL_DIR"

# پشتیبان‌گیری ایمن از دیتابیس قبل از آپدیت
if [[ -f "data/resibot.db" ]]; then
  bold "==> پشتیبان‌گیری از دیتابیس"
  mkdir -p backups
  cp -f "data/resibot.db" "backups/resibot-$(date +%Y%m%d-%H%M%S).db"
fi

bold "==> دریافت آخرین کد (داده‌ها در data/ و .env دست‌نخورده می‌مانند)"
# نکته‌ی مهم: ممکن است روی سرور فایل‌های ردیابی‌شده به‌صورت محلی تغییر کرده باشند
# (مثلاً توسط اسکریپت‌های نصب ربات کمکی) یا فایل‌های ردیابی‌نشده‌ای مثل customerbot/
# ساخته شده باشند. برای اینکه آپدیت هیچ‌وقت به خاطر تعارض گیر نکند، به‌جای
# pull، به‌صورت اجباری با نسخه‌ی ریموت هم‌تراز می‌شویم.
#  - .env و data/ و *.db و .venv/ در .gitignore هستند و لمس نمی‌شوند.
#  - backups/ ردیابی‌نشده و خارج از مخزن است و حفظ می‌شود.
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)"
if [[ -z "$CURRENT_BRANCH" || "$CURRENT_BRANCH" == "HEAD" ]]; then
  CURRENT_BRANCH="main"
fi
git fetch origin --prune
# تلاش برای fast-forward ساده؛ اگر به خاطر تغییرات محلی نشد، reset اجباری
if ! git merge --ff-only "origin/${CURRENT_BRANCH}" >/dev/null 2>&1; then
  bold "   (تغییرات محلی شناسایی شد؛ هم‌ترازسازی اجباری با ریموت)"
  git reset --hard "origin/${CURRENT_BRANCH}"
fi

bold "==> به‌روزرسانی وابستگی‌ها"
if [[ ! -d ".venv" ]]; then
  python3 -m venv .venv
fi
./.venv/bin/pip install --upgrade pip >/dev/null
./.venv/bin/pip install -r requirements.txt

bold "==> ری‌استارت سرویس"
systemctl restart "$SERVICE_NAME"

sleep 2
systemctl --no-pager --lines=10 status "$SERVICE_NAME" || true

# ربات کمکی مشتری (اگر سرویسش نصب شده باشد یا توکنش تنظیم شده باشد)
CUSTOMER_SERVICE_NAME="resibot-customer"
if [[ -f "$INSTALL_DIR/resibot-customer.service" ]] && grep -qE "^CUSTOMER_BOT_TOKEN=.+" "$INSTALL_DIR/.env" 2>/dev/null; then
  bold "==> به‌روزرسانی/ری‌استارت سرویس ربات کمکی مشتری"
  CUSTOMER_SERVICE_PATH="/etc/systemd/system/${CUSTOMER_SERVICE_NAME}.service"
  sed "s#__INSTALL_DIR__#${INSTALL_DIR}#g" "$INSTALL_DIR/resibot-customer.service" > "$CUSTOMER_SERVICE_PATH"
  systemctl daemon-reload
  systemctl enable "$CUSTOMER_SERVICE_NAME" >/dev/null 2>&1 || true
  systemctl restart "$CUSTOMER_SERVICE_NAME"
  sleep 2
  systemctl --no-pager --lines=10 status "$CUSTOMER_SERVICE_NAME" || true
fi

green ""
green "✅ آپدیت کامل شد. دیتابیس و تنظیمات حفظ شدند."
