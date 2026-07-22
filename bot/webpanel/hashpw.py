"""ابزار خط‌فرمان برای ساخت هش امن رمز پنل وب.

استفاده:
    python -m bot.webpanel.hashpw
سپس رمز را وارد کنید؛ خروجی را در WEB_PANEL_PASSWORD در فایل .env بگذارید تا
رمز خام روی سرور ذخیره نشود.
"""
from __future__ import annotations

import getpass
import sys

from .security import hash_password, verify_password


def main() -> None:
    try:
        p1 = getpass.getpass("رمز عبور پنل وب: ")
        p2 = getpass.getpass("تکرار رمز عبور: ")
    except (EOFError, KeyboardInterrupt):
        print("\nلغو شد.")
        sys.exit(1)
    if not p1:
        print("رمز خالی است.")
        sys.exit(1)
    if p1 != p2:
        print("رمزها یکسان نیستند.")
        sys.exit(1)
    h = hash_password(p1)
    assert verify_password(p1, h)
    print("\nهش امن (این خط را در .env بگذارید):\n")
    print(f"WEB_PANEL_PASSWORD={h}")


if __name__ == "__main__":
    main()
