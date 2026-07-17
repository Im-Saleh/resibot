"""پرداخت مستقیم USDT روی شبکه‌ی BEP20 (BSC) — فقط رصد (watch-only).

فلسفه‌ی امنیتی:
  * هیچ کلید خصوصی‌ای روی سرور ذخیره نمی‌شود. ما فقط بلاکچین را «می‌خوانیم».
  * پول مشتری مستقیم به ولت مقصد (ولت خود ادمین) واریز می‌شود؛ هیچ فورواردی
    انجام نمی‌شود، پس هیچ گس/فی انتقالی هم وجود ندارد → صفر فی واقعی.
  * تطبیق پرداخت با «مبلغ یکتا»: هر فاکتور یک مبلغ منحصربه‌فرد دارد تا واریز
    ورودی دقیقاً به همان سفارش وصل شود.

مکانیزم‌های ضدتقلب:
  1. فقط رویدادهای Transfer که از «قرارداد رسمی USDT روی BSC» صادر شده باشند
     پذیرفته می‌شوند → تتر فیک (توکن‌های تقلبی هم‌نام) رد می‌شوند.
  2. مقصد تراکنش باید دقیقاً ولت مقصد ما باشد.
  3. مبلغ باید با مبلغ یکتای فاکتور مطابقت داشته باشد.
  4. حداقل تعداد تأیید (confirmations) لازم است تا ری‌ارگ/تراکنش تأییدنشده
     پذیرفته نشود.
  5. هر هش تراکنش فقط یک‌بار می‌تواند یک فاکتور را تسویه کند (ضدری‌پلی؛
     در سطح دیتابیس با ایندکس یکتا تضمین شده).
  6. فقط واریزهای بعد از ساخت فاکتور (بلاک ≥ start_block) معتبرند.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Awaitable, Callable, Optional

import httpx

logger = logging.getLogger("resibot.crypto")

# قرارداد رسمی USDT (Binance-Peg) روی BSC. تشخیص تتر واقعی از فیک بر همین اساس است.
USDT_BEP20_CONTRACT = "0x55d398326f99059ff775485246999027b3197955"
USDT_BEP20_DECIMALS = 18
# keccak256("Transfer(address,address,uint256)")
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

# متد سلکتور توابع استاندارد ERC20 (برای روش تشخیص با اسکن بلاک)
TRANSFER_SELECTOR = "0xa9059cbb"      # transfer(address,uint256)
TRANSFERFROM_SELECTOR = "0x23b872dd"  # transferFrom(address,address,uint256)

_ADDR_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
_TXHASH_RE = re.compile(r"0x[0-9a-fA-F]{64}")

_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# سقف بازه‌ی هر درخواست eth_getLogs. اکثر RPCهای عمومی BSC بازه را به ۲۵ تا ۵۰
# بلاک محدود می‌کنند؛ پس محافظه‌کارانه ۲۰ می‌گذاریم تا همه‌جا کار کند.
GETLOGS_CHUNK = 20
# سقف کل بلاک‌هایی که در یک دور رصد به عقب اسکن می‌شوند (سقف امن برای جلوگیری از
# فشار به RPC؛ TTL معمولی فاکتور ~۶۰ دقیقه ≈ ۱۲۰۰ بلاک را پوشش می‌دهد).
MAX_BACKFILL_BLOCKS = 2000
# سقف بلاک‌هایی که در روش «اسکن بلاک» (fallback جهانی) در هر دور اسکن می‌شوند.
BLOCKSCAN_WINDOW = 40

# لیست پیش‌فرض RPCهای عمومی و رایگانِ BSC که eth_getLogs را پشتیبانی می‌کنند
# (تست‌شده). استخر RPC بین این‌ها جابه‌جا می‌شود تا اگر یکی خراب/محدود شد،
# تأیید خودکار بدون وقفه از بقیه ادامه یابد. bsc-dataseed برای receipt/block هم
# عالی است (روش fallback اسکن بلاک).
DEFAULT_BSC_RPCS: list[str] = [
    "https://bsc-rpc.publicnode.com",
    "https://bsc.publicnode.com",
    "https://bsc-pokt.nodies.app",
    "https://bsc.rpc.blxrbdn.com",
    "https://1rpc.io/bnb",
    "https://bsc-mainnet.public.blastapi.io",
    "https://bsc-dataseed.binance.org",
    "https://bsc-dataseed1.bnbchain.org",
]


def is_valid_address(addr: str) -> bool:
    """اعتبارسنجی فرمت آدرس EVM (0x + ۴۰ رقم هگز). ضدتزریق: هیچ کاراکتر دیگری مجاز نیست."""
    return bool(_ADDR_RE.match((addr or "").strip()))


def normalize_address(addr: str) -> str:
    return (addr or "").strip().lower()


def _addr_topic(addr: str) -> str:
    """آدرس را به فرمت topic (۳۲ بایت، صفرپرشده از چپ) تبدیل می‌کند."""
    a = normalize_address(addr)
    return "0x" + "0" * 24 + a[2:]


def extract_tx_hash(text: str) -> str:
    """هش تراکنش را از متن یا لینک bscscan استخراج می‌کند."""
    m = _TXHASH_RE.search((text or "").strip())
    return m.group(0).lower() if m else ""


def units_to_usdt(raw: int) -> float:
    return raw / (10 ** USDT_BEP20_DECIMALS)


class BscRpcError(Exception):
    pass


class BscRpc:
    """کلاینت سبک JSON-RPC برای BSC روی httpx (بدون وابستگی سنگین web3)."""

    def __init__(self, url: str, *, timeout: float = 20.0) -> None:
        self.url = url.strip()
        self._timeout = timeout
        self._id = 0

    async def _call(self, method: str, params: list[Any]) -> Any:
        self._id += 1
        body = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}
        # برخی RPCها (مثل publicnode) بدون User-Agent مرورگری، درخواست را 403 می‌کنند.
        headers = {"Content-Type": "application/json", "User-Agent": _UA}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(self.url, json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise BscRpcError(f"خطای شبکه RPC: {exc}") from exc
        if resp.status_code >= 400:
            raise BscRpcError(f"RPC خطا (HTTP {resp.status_code}): {resp.text[:200]}")
        try:
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            raise BscRpcError(f"پاسخ نامعتبر RPC: {exc}") from exc
        if isinstance(data, dict) and data.get("error"):
            raise BscRpcError(f"RPC error: {data['error']}")
        return data.get("result") if isinstance(data, dict) else None

    async def block_number(self) -> int:
        result = await self._call("eth_blockNumber", [])
        return int(result, 16) if result else 0

    async def get_transfer_logs(
        self, *, to_address: str, from_block: int, to_block: int
    ) -> list[dict[str, Any]]:
        """رویدادهای Transfer قرارداد USDT به آدرس مقصد را در بازه‌ی بلاک برمی‌گرداند.

        فیلتر شامل آدرس قرارداد USDT است؛ پس فقط تترِ واقعی برگردانده می‌شود.
        بازه به تکه‌های کوچک شکسته می‌شود تا محدودیت RPCهای عمومی نقض نشود.
        """
        logs: list[dict[str, Any]] = []
        start = max(0, from_block)
        first = True
        while start <= to_block:
            end = min(start + GETLOGS_CHUNK - 1, to_block)
            params = [{
                "fromBlock": hex(start),
                "toBlock": hex(end),
                "address": USDT_BEP20_CONTRACT,
                "topics": [TRANSFER_TOPIC, None, _addr_topic(to_address)],
            }]
            if not first:
                # مکث کوتاه بین تکه‌ها تا به محدودیت نرخ RPC نخوریم.
                await asyncio.sleep(0.12)
            first = False
            chunk = await self._call("eth_getLogs", params)
            if isinstance(chunk, list):
                logs.extend(chunk)
            start = end + 1
        return logs

    async def get_transaction_receipt(self, tx_hash: str) -> Optional[dict[str, Any]]:
        return await self._call("eth_getTransactionReceipt", [tx_hash])

    async def get_block_with_txs(self, block_number: int) -> Optional[dict[str, Any]]:
        return await self._call("eth_getBlockByNumber", [hex(block_number), True])


class TransferMatch:
    """یک واریز USDT شناسایی‌شده روی زنجیره."""

    __slots__ = ("tx_hash", "to_address", "amount", "block_number")

    def __init__(self, tx_hash: str, to_address: str, amount: float, block_number: int) -> None:
        self.tx_hash = tx_hash.lower()
        self.to_address = to_address.lower()
        self.amount = amount
        self.block_number = block_number


def parse_transfer_log(log: dict[str, Any]) -> Optional[TransferMatch]:
    """یک لاگ Transfer را به TransferMatch تبدیل می‌کند (با اعتبارسنجی کامل).

    فقط لاگ‌هایی که از قرارداد رسمی USDT و با امضای Transfer باشند پذیرفته می‌شوند.
    """
    try:
        if normalize_address(log.get("address", "")) != USDT_BEP20_CONTRACT:
            return None
        topics = log.get("topics") or []
        if len(topics) < 3 or (topics[0] or "").lower() != TRANSFER_TOPIC:
            return None
        to_addr = "0x" + topics[2][-40:]
        raw = int(log.get("data", "0x0"), 16)
        amount = units_to_usdt(raw)
        block_number = int(log.get("blockNumber", "0x0"), 16)
        tx_hash = (log.get("transactionHash") or "").lower()
        if not tx_hash:
            return None
        return TransferMatch(tx_hash, to_addr, amount, block_number)
    except (ValueError, TypeError, IndexError, KeyError):
        return None


def decode_usdt_tx(tx: dict[str, Any], targets: set[str]) -> Optional[TransferMatch]:
    """یک تراکنش خام بلاک را که مستقیماً قرارداد USDT را صدا زده رمزگشایی می‌کند.

    این «روش اسکن بلاک» است که روی هر RPCی کار می‌کند (eth_getBlockByNumber جهانی
    است) و به eth_getLogs نیاز ندارد. فقط transfer/transferFrom روی قرارداد رسمی
    USDT را می‌پذیرد → تتر فیک خود‌به‌خود رد می‌شود.

    نکته: چون از ورودی تراکنش می‌خوانیم (نه رسید)، پیش از تسویه حتماً باید با
    verify_deposit_tx (رسید) تأیید نهایی شود تا تراکنش‌های ناموفق/revert رد شوند.
    """
    try:
        if normalize_address(tx.get("to", "")) != USDT_BEP20_CONTRACT:
            return None
        inp = (tx.get("input") or tx.get("data") or "0x").lower()
        if len(inp) < 10:
            return None
        selector = inp[:10]
        payload = inp[10:]
        if selector == TRANSFER_SELECTOR:
            if len(payload) < 128:
                return None
            to_addr = "0x" + payload[24:64]
            amount_raw = int(payload[64:128], 16)
        elif selector == TRANSFERFROM_SELECTOR:
            if len(payload) < 192:
                return None
            to_addr = "0x" + payload[88:128]
            amount_raw = int(payload[128:192], 16)
        else:
            return None
        to_addr = to_addr.lower()
        if to_addr not in targets:
            return None
        block_number = int(tx.get("blockNumber", "0x0"), 16)
        tx_hash = (tx.get("hash") or "").lower()
        if not tx_hash:
            return None
        return TransferMatch(tx_hash, to_addr, units_to_usdt(amount_raw), block_number)
    except (ValueError, TypeError, IndexError, KeyError):
        return None


def amount_matches(received: float, expected: float, *, tolerance: float = 0.0005) -> bool:
    """تطبیق نزدیک-دقیق مبلغ (به‌خاطر مبالغ یکتای فاصله‌دار، دقیق کافی است).

    اجازه‌ی «کمی بیشتر» می‌دهد ولی «کمتر» را رد می‌کند.
    """
    return received >= (expected - tolerance)


class RpcPool:
    """استخری از چند RPC با failover خودکار.

    هر فراخوانی از RPC فعلی شروع می‌شود؛ اگر خطا داد (خرابی/محدودیت نرخ/عدم
    پشتیبانی)، به‌ترتیب بقیه‌ی RPCها امتحان می‌شوند. به این ترتیب اگر یکی از
    سرویس‌ها خراب شود، تأیید خودکار بدون وقفه از بقیه ادامه می‌یابد.
    """

    def __init__(self, urls: list[str], *, timeout: float = 15.0) -> None:
        seen: set[str] = set()
        ordered: list[str] = []
        for u in urls:
            u = (u or "").strip()
            if u and u not in seen:
                seen.add(u)
                ordered.append(u)
        if not ordered:
            ordered = list(DEFAULT_BSC_RPCS)
        self.rpcs = [BscRpc(u, timeout=timeout) for u in ordered]
        self._i = 0

    @property
    def urls(self) -> list[str]:
        return [r.url for r in self.rpcs]

    async def _call(self, method: str, params: list[Any]) -> Any:
        last_exc: Optional[Exception] = None
        n = len(self.rpcs)
        for k in range(n):
            idx = (self._i + k) % n
            try:
                res = await self.rpcs[idx]._call(method, params)
                self._i = idx  # روی همان RPC سالم می‌مانیم
                return res
            except BscRpcError as exc:
                last_exc = exc
                continue
        raise last_exc or BscRpcError("هیچ RPC سالمی در دسترس نبود.")

    async def block_number(self) -> int:
        result = await self._call("eth_blockNumber", [])
        return int(result, 16) if result else 0

    async def get_transaction_receipt(self, tx_hash: str) -> Optional[dict[str, Any]]:
        return await self._call("eth_getTransactionReceipt", [tx_hash])

    async def get_block_with_txs(self, block_number: int) -> Optional[dict[str, Any]]:
        return await self._call("eth_getBlockByNumber", [hex(block_number), True])

    async def get_transfer_logs(
        self, *, to_address: str, from_block: int, to_block: int
    ) -> list[dict[str, Any]]:
        """رویدادهای Transfer قرارداد USDT به آدرس مقصد را در بازه برمی‌گرداند.

        در تکه‌های کوچک (برای رعایت محدودیت RPCها) و با failover بین RPCها.
        اگر همه‌ی RPCها eth_getLogs را رد کنند، خطا می‌دهد تا روش «اسکن بلاک»
        جایگزین شود.
        """
        logs: list[dict[str, Any]] = []
        start = max(0, from_block)
        first = True
        while start <= to_block:
            end = min(start + GETLOGS_CHUNK - 1, to_block)
            params = [{
                "fromBlock": hex(start),
                "toBlock": hex(end),
                "address": USDT_BEP20_CONTRACT,
                "topics": [TRANSFER_TOPIC, None, _addr_topic(to_address)],
            }]
            if not first:
                await asyncio.sleep(0.1)
            first = False
            chunk = await self._call("eth_getLogs", params)
            if isinstance(chunk, list):
                logs.extend(chunk)
            start = end + 1
        return logs

    async def scan_block_transfers(
        self, *, targets: set[str], from_block: int, to_block: int
    ) -> list[TransferMatch]:
        """روش fallback جهانی: بلاک‌ها را می‌خواند و واریزهای مستقیم USDT به
        آدرس‌های مقصد را از ورودی تراکنش‌ها استخراج می‌کند (بدون eth_getLogs)."""
        found: list[TransferMatch] = []
        for bn in range(max(0, from_block), to_block + 1):
            block = await self.get_block_with_txs(bn)
            if not block:
                continue
            for tx in block.get("transactions", []) or []:
                if not isinstance(tx, dict):
                    continue
                m = decode_usdt_tx(tx, targets)
                if m is not None:
                    # blockNumber ممکن است در تراکنش نباشد؛ از خود بلاک می‌گیریم.
                    if m.block_number == 0:
                        m.block_number = bn
                    found.append(m)
            await asyncio.sleep(0.03)
        return found


class CryptoWatcher:
    """حلقه‌ی پس‌زمینه که ولت مقصد را برای واریزهای USDT رصد می‌کند.

    وقتی واریزی با مبلغ یکتای یک فاکتورِ در انتظار پیدا شد و به تعداد کافی تأیید
    خورد، تابع settle (تزریق‌شده) را صدا می‌زند تا فاکتور تسویه و محصول تحویل شود.
    """

    def __init__(
        self,
        *,
        pool: "RpcPool",
        db: Any,
        get_confirmations: Callable[[], int],
        settle: Callable[[str, str], Awaitable[None]],
        poll_interval: float = 15.0,
    ) -> None:
        self.pool = pool
        self.db = db
        self._get_confirmations = get_confirmations
        self._settle = settle
        self._poll_interval = poll_interval
        self._stopped = False
        self._blockscan_notified = False

    def stop(self) -> None:
        self._stopped = True

    async def run(self) -> None:
        logger.info(
            "رصدگر پرداخت کریپتو (USDT BEP20) شروع شد | %d RPC در استخر.",
            len(self.pool.rpcs),
        )
        while not self._stopped:
            try:
                await self._tick()
            except asyncio.CancelledError:  # noqa: PERF203
                raise
            except Exception:  # noqa: BLE001
                logger.exception("خطا در دور رصد کریپتو (نادیده گرفته شد، ادامه می‌دهیم)")
            await asyncio.sleep(self._poll_interval)

    async def _tick(self) -> None:
        # فاکتورهای منقضی را می‌بندیم تا مبالغ یکتاشان آزاد شود.
        self.db.expire_stale_crypto_payments()

        waiting = self.db.list_waiting_crypto_payments()
        if not waiting:
            return
        try:
            current = await self.pool.block_number()
        except BscRpcError:
            logger.warning("همه‌ی RPCها برای گرفتن شماره بلاک ناموفق بودند؛ دور بعد.")
            return
        if current <= 0:
            return

        required_conf = max(1, int(self._get_confirmations()))
        buffer = required_conf + 8
        starts = [int(p["start_block"] or 0) for p in waiting if int(p["start_block"] or 0) > 0]
        oldest = min(starts) if starts else current

        # آدرس‌های مقصدِ یکتا در میان فاکتورهای در انتظار.
        addresses = {
            normalize_address(p["pay_address"]) for p in waiting if p["pay_address"]
        }
        if not addresses:
            return

        # ---------- روش ۱: eth_getLogs (اصلی، سبک) ----------
        matches: list[TransferMatch] = []
        getlogs_ok = True
        from_block = max(0, oldest - buffer, current - MAX_BACKFILL_BLOCKS)
        for addr in addresses:
            try:
                raw_logs = await self.pool.get_transfer_logs(
                    to_address=addr, from_block=from_block, to_block=current
                )
                for lg in raw_logs:
                    m = parse_transfer_log(lg)
                    if m is not None:
                        matches.append(m)
            except BscRpcError:
                getlogs_ok = False
                break

        # ---------- روش ۲: اسکن بلاک (fallback جهانی) ----------
        if not getlogs_ok:
            if not self._blockscan_notified:
                logger.info(
                    "eth_getLogs روی هیچ RPCی در دسترس نبود؛ روش جایگزین «اسکن بلاک» فعال شد."
                )
                self._blockscan_notified = True
            scan_from = max(0, current - BLOCKSCAN_WINDOW)
            try:
                matches = await self.pool.scan_block_transfers(
                    targets=addresses, from_block=scan_from, to_block=current
                )
            except BscRpcError:
                logger.warning("روش اسکن بلاک هم ناموفق بود؛ دور بعد دوباره تلاش می‌کنیم.")
                return

        if not matches:
            return

        for m in matches:
            confs = current - m.block_number + 1
            if confs < required_conf:
                continue
            if self.db.tx_hash_used(m.tx_hash):
                continue
            payment = self._find_payment(waiting, m)
            if payment is None:
                continue
            order_id = payment["order_id"]
            # تأیید نهایی و قطعی با رسید تراکنش (ضدتقلب؛ تراکنش‌های ناموفق/جعلی رد می‌شوند).
            ok, _msg, _amt = await verify_deposit_tx(
                self.pool, m.tx_hash,
                to_address=payment["pay_address"],
                min_amount=float(payment["pay_amount"]),
                required_conf=required_conf,
                min_block=int(payment["start_block"] or 0),
            )
            if not ok:
                continue
            try:
                await self._settle(order_id, m.tx_hash)
                logger.info(
                    "پرداخت کریپتو تسویه شد: order=%s tx=%s amount=%s",
                    order_id, m.tx_hash, m.amount,
                )
            except Exception:  # noqa: BLE001
                logger.exception("تسویه‌ی پرداخت کریپتو ناموفق بود (order=%s)", order_id)

    @staticmethod
    def _find_payment(waiting: list, m: TransferMatch) -> Optional[Any]:
        """فاکتور در انتظاری که آدرس و مبلغ و بلاکش با این واریز می‌خواند."""
        best = None
        for p in waiting:
            if normalize_address(p["pay_address"]) != m.to_address:
                continue
            expected = round(float(p["pay_amount"]), 6)
            if expected <= 0:
                continue
            if m.block_number < int(p["start_block"] or 0):
                continue  # واریز قبل از ساخت فاکتور — نامعتبر
            if not amount_matches(m.amount, expected):
                continue
            # نزدیک‌ترین مبلغ را انتخاب می‌کنیم تا واریز به فاکتور درست بچسبد.
            if best is None or expected > round(float(best["pay_amount"]), 6):
                if m.amount + 0.0005 >= expected:
                    best = p
        return best



async def verify_deposit_tx(
    rpc: Any,
    tx_hash: str,
    *,
    to_address: str,
    min_amount: float,
    required_conf: int,
    min_block: int = 0,
) -> tuple[bool, str, float]:
    """`rpc` می‌تواند BscRpc یا RpcPool باشد (هر دو get_transaction_receipt و
    block_number دارند)."""
    """یک هش تراکنش را برای یک فاکتور مشخص راستی‌آزمایی می‌کند.

    برمی‌گرداند: (موفق، پیام، مبلغ_USDT_واریزشده_به_مقصد).
    همه‌ی بررسی‌های ضدتقلب (قرارداد رسمی USDT، آدرس مقصد، مبلغ، تأیید، بلاک) اعمال می‌شود.
    """
    tx_hash = extract_tx_hash(tx_hash)
    if not tx_hash:
        return (False, "هش تراکنش نامعتبر است.", 0.0)
    try:
        receipt = await rpc.get_transaction_receipt(tx_hash)
    except BscRpcError as exc:
        return (False, f"خطا در ارتباط با شبکه: {exc}", 0.0)
    if not receipt:
        return (False, "تراکنش پیدا نشد یا هنوز در بلاکچین ثبت نشده است.", 0.0)
    if str(receipt.get("status", "")).lower() not in ("0x1", "1"):
        return (False, "این تراکنش روی شبکه ناموفق بوده است.", 0.0)

    try:
        block = int(receipt.get("blockNumber", "0x0"), 16)
    except (ValueError, TypeError):
        block = 0
    try:
        current = await rpc.block_number()
    except BscRpcError:
        current = 0
    confs = (current - block + 1) if (current and block) else 0

    target = normalize_address(to_address)
    total_to = 0.0
    for lg in receipt.get("logs") or []:
        m = parse_transfer_log(lg)
        if m is not None and m.to_address == target:
            total_to += m.amount

    if total_to <= 0:
        return (
            False,
            "در این تراکنش هیچ واریز USDT معتبری (تترِ واقعی BEP20) به آدرس مقصد پیدا نشد. "
            "اگر توکن دیگری فرستاده‌اید پذیرفته نمی‌شود.",
            0.0,
        )
    if min_block and block and block < min_block:
        return (False, "این تراکنش مربوط به قبل از ساخت این فاکتور است و معتبر نیست.", total_to)
    if not amount_matches(total_to, min_amount):
        return (
            False,
            f"مبلغ واریزشده ({total_to:g} USDT) کمتر از مبلغ فاکتور ({min_amount:g} USDT) است.",
            total_to,
        )
    if confs < max(1, int(required_conf)):
        return (
            False,
            f"تراکنش پیدا شد ولی هنوز به‌قدر کافی تأیید نخورده است "
            f"({confs}/{required_conf} تأیید). چند دقیقه بعد دوباره تلاش کنید.",
            total_to,
        )
    return (True, "ok", total_to)
