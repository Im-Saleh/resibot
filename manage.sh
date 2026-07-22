#!/usr/bin/env bash
# ============================================================
#  resibot — ابزار مدیریت و نگهداری (DevOps)
#  اجرا:  bash /opt/resibot/manage.sh <دستور>
#
#  دستورها:
#    status      وضعیت سرویس‌ها
#    logs        لاگ زنده‌ی ربات (journalctl -f)
#    weblogs     فقط لاگ‌های مربوط به پنل وب
#    restart     ری‌استارت ربات (و ربات کمکی در صورت وجود)
#    update      به‌روزرسانی امن کد (با حفظ دیتابیس)
#    backup      تهیه‌ی پشتیبان فوری از دیتابیس (با چرخش نگهداری)
#    restore <f> بازگردانی دیتابیس از فایل پشتیبان
#    health      بررسی سلامت ربات و پنل وب (HTTP health)
#    webpass     ساخت هش امن رمز پنل وب و راهنمای ثبت آن
#    audit       نمایش ۳۰ رخداد امنیتی اخیر از دیتابیس
#    maintenance on|off   روشن/خاموش کردن حالت تعمیر
# ============================================================
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/resibot}"
SERVICE_NAME="resibot"
CUSTOMER_SERVICE_NAME="resibot-customer"
DB_FILE="$INSTALL_DIR/data/resibot.db"
PY="$INSTALL_DIR/.venv/bin/python"
BACKUP_KEEP="${BACKUP_KEEP:-20}"

green() { printf "\033[32m%s\033[0m\n" "$*"; }
bold()  { printf "\033[1m%s\033[0m\n" "$*"; }
red()   { printf "\033[31m%s\033[0m\n" "$*"; }

_port() { # استخراج مقدار یک کلید از .env
  grep -E "^$1=" "$INSTALL_DIR/.env" 2>/dev/null | head -n1 | cut -d= -f2- || true
}

cmd="${1:-help}"; shift || true

case "$cmd" in
  status)
    systemctl --no-pager --lines=15 status "$SERVICE_NAME" || true
    if systemctl list-unit-files | grep -q "$CUSTOMER_SERVICE_NAME"; then
      echo; systemctl --no-pager --lines=8 status "$CUSTOMER_SERVICE_NAME" || true
    fi
    ;;

  logs)
    journalctl -u "$SERVICE_NAME" -f
    ;;

  weblogs)
    journalctl -u "$SERVICE_NAME" -f | grep --line-buffered -i "webpanel\|پنل وب"
    ;;

  restart)
    systemctl restart "$SERVICE_NAME"
    green "✅ سرویس ری‌استارت شد."
    systemctl --no-pager --lines=8 status "$SERVICE_NAME" || true
    ;;

  update)
    bash "$INSTALL_DIR/update.sh"
    ;;

  backup)
    mkdir -p "$INSTALL_DIR/backups"
    if [[ ! -f "$DB_FILE" ]]; then red "دیتابیس پیدا نشد: $DB_FILE"; exit 1; fi
    TS="$(date +%Y%m%d-%H%M%S)"
    OUT="$INSTALL_DIR/backups/resibot-$TS.db"
    # پشتیبان سازگار با WAL از طریق دستور رسمی sqlite
    "$PY" - "$DB_FILE" "$OUT" <<'PYEOF'
import sqlite3, sys
src, dst = sys.argv[1], sys.argv[2]
s = sqlite3.connect(src); d = sqlite3.connect(dst)
with d: s.backup(d)
s.close(); d.close()
print("ok")
PYEOF
    green "✅ پشتیبان ساخته شد: $OUT"
    # چرخش: فقط N نسخه‌ی اخیر نگه داشته می‌شود
    ls -1t "$INSTALL_DIR"/backups/resibot-*.db 2>/dev/null | tail -n +$((BACKUP_KEEP+1)) | xargs -r rm -f
    green "🧹 فقط $BACKUP_KEEP پشتیبان اخیر نگه داشته شد."
    ;;

  restore)
    SRC="${1:-}"
    if [[ -z "$SRC" || ! -f "$SRC" ]]; then red "فایل پشتیبان معتبر بدهید: manage.sh restore <file.db>"; exit 1; fi
    bold "قبل از بازگردانی، از وضعیت فعلی پشتیبان می‌گیریم..."
    cp -f "$DB_FILE" "$INSTALL_DIR/backups/pre-restore-$(date +%Y%m%d-%H%M%S).db" 2>/dev/null || true
    systemctl stop "$SERVICE_NAME" || true
    cp -f "$SRC" "$DB_FILE"
    rm -f "$DB_FILE-wal" "$DB_FILE-shm" 2>/dev/null || true
    systemctl start "$SERVICE_NAME" || true
    green "✅ دیتابیس بازگردانی شد و سرویس دوباره اجرا شد."
    ;;

  health)
    IPN_PORT="$(_port IPN_PORT)"; WEB_PORT="$(_port WEB_PANEL_PORT)"
    IPN_PORT="${IPN_PORT:-8090}"; WEB_PORT="${WEB_PORT:-8095}"
    echo "— سرویس —"; systemctl is-active "$SERVICE_NAME" || true
    echo "— پنل وب (پورت $WEB_PORT) —"
    curl -fsS --max-time 5 "http://127.0.0.1:${WEB_PORT}/panel/health" && echo " ✅" || red " ❌ در دسترس نیست"
    echo "— سرور IPN (پورت $IPN_PORT) —"
    curl -fsS --max-time 5 "http://127.0.0.1:${IPN_PORT}/health" && echo " ✅" || echo " (شاید غیرفعال/HTTPS)"
    ;;

  webpass)
    "$PY" -m bot.webpanel.hashpw
    echo
    bold "این مقدار را در $INSTALL_DIR/.env جای WEB_PANEL_PASSWORD بگذارید و سپس:"
    echo "  bash $INSTALL_DIR/manage.sh restart"
    ;;

  audit)
    "$PY" - <<'PYEOF'
import os, datetime
os.chdir(os.environ.get("INSTALL_DIR", "/opt/resibot"))
from bot.config import settings
from bot.database import Database
db = Database(settings.db_full_path())
for r in db.list_audit(limit=30):
    ts = datetime.datetime.fromtimestamp(int(r["ts"])).strftime("%Y-%m-%d %H:%M:%S")
    print(f"{ts} | {r['action']:22} | {r['actor'] or '-':>12} | {r['ip'] or '-':>15} | {r['detail'] or ''}")
db.close()
PYEOF
    ;;

  maintenance)
    MODE="${1:-}"
    case "$MODE" in
      on)  VAL=1 ;;
      off) VAL=0 ;;
      *) red "استفاده: manage.sh maintenance on|off"; exit 1 ;;
    esac
    INSTALL_DIR="$INSTALL_DIR" "$PY" - "$VAL" <<'PYEOF'
import os, sys
os.chdir(os.environ.get("INSTALL_DIR", "/opt/resibot"))
from bot.config import settings
from bot.database import Database
db = Database(settings.db_full_path())
db.set_setting("maintenance_mode", sys.argv[1])
db.audit("maintenance_toggle", actor="cli", detail="on" if sys.argv[1]=="1" else "off")
db.close()
print("maintenance_mode =", sys.argv[1])
PYEOF
    green "✅ اعمال شد."
    ;;

  *)
    bold "resibot manage — دستورهای موجود:"
    echo "  status | logs | weblogs | restart | update | backup | restore <file>"
    echo "  health | webpass | audit | maintenance on|off"
    ;;
esac
