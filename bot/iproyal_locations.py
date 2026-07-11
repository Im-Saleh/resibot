"""دیتاست کشور/شهر برای رزیدنتال ۲ (IPRoyal).

IPRoyal پارامترهای لوکیشن را داخل رشته‌ی password کدگذاری می‌کند و پوشش کشوری
گسترده‌ای دارد (نگاه کنید به https://iproyal.com/proxies-by-location/). اینجا
کشورهای پرکاربرد و شهرهای اصلی هر کدام را نگه می‌داریم؛ کاربر می‌تواند هر کد
کشور دلخواه دیگری را هم دستی/با جستجو انتخاب کند.

نام شهرها به‌صورت CamelCase و بدون فاصله‌اند (برای نمایش با prettify فاصله‌گذاری
می‌شوند). هنگام ساخت رشته‌ی IPRoyal این نام‌ها با حروف کوچک ارسال می‌شوند.
"""
from __future__ import annotations

from . import countries

# country_code -> [city_names]
CITIES: dict[str, list[str]] = {
    "US": [
        "NewYork", "LosAngeles", "Chicago", "Houston", "Miami",
        "Dallas", "SanFrancisco", "Seattle", "Atlanta", "Ashburn",
    ],
    "GB": ["London", "Manchester", "Birmingham", "Glasgow", "Liverpool", "Leeds"],
    "DE": ["Berlin", "Munich", "Frankfurt", "Hamburg", "Cologne", "Dusseldorf"],
    "FR": ["Paris", "Marseille", "Lyon", "Toulouse", "Nice"],
    "NL": ["Amsterdam", "Rotterdam", "TheHague", "Utrecht", "Eindhoven"],
    "CA": ["Toronto", "Montreal", "Vancouver", "Calgary", "Ottawa"],
    "IT": ["Rome", "Milan", "Naples", "Turin", "Florence"],
    "ES": ["Madrid", "Barcelona", "Valencia", "Seville", "Malaga"],
    "TR": ["Istanbul", "Ankara", "Izmir", "Bursa", "Antalya"],
    "AE": ["Dubai", "AbuDhabi", "Sharjah"],
    "SE": ["Stockholm", "Gothenburg", "Malmo"],
    "PL": ["Warsaw", "Krakow", "Wroclaw", "Poznan"],
    "JP": ["Tokyo", "Osaka", "Yokohama", "Nagoya"],
    "SG": ["Singapore"],
    "AU": ["Sydney", "Melbourne", "Brisbane", "Perth"],
    "IN": ["Mumbai", "Delhi", "Bangalore", "Chennai", "Hyderabad"],
    "BR": ["SaoPaulo", "RioDeJaneiro", "Brasilia", "Salvador"],
    "RU": ["Moscow", "SaintPetersburg", "Novosibirsk"],
    "CH": ["Zurich", "Geneva", "Bern", "Basel"],
    "BE": ["Brussels", "Antwerp", "Ghent"],
    "AT": ["Vienna", "Graz", "Linz", "Salzburg"],
    "FI": ["Helsinki", "Espoo", "Tampere"],
    "NO": ["Oslo", "Bergen", "Trondheim"],
    "DK": ["Copenhagen", "Aarhus", "Odense"],
    "IE": ["Dublin", "Cork", "Galway"],
    "PT": ["Lisbon", "Porto", "Braga"],
    "KR": ["Seoul", "Busan", "Incheon"],
    "HK": ["HongKong"],
    "MX": ["MexicoCity", "Guadalajara", "Monterrey"],
    "ID": ["Jakarta", "Surabaya", "Bandung"],
    "MY": ["KualaLumpur", "GeorgeTown", "JohorBahru"],
    "TH": ["Bangkok", "ChiangMai", "Phuket"],
    "VN": ["Hanoi", "HoChiMinhCity", "DaNang"],
    "ZA": ["Johannesburg", "CapeTown", "Durban"],
    "SA": ["Riyadh", "Jeddah", "Mecca"],
    "RO": ["Bucharest", "ClujNapoca", "Timisoara"],
    "CZ": ["Prague", "Brno", "Ostrava"],
    "GR": ["Athens", "Thessaloniki"],
    "UA": ["Kyiv", "Kharkiv", "Odesa"],
}

# کشورهای پرکاربردِ IPRoyal برای دکمه‌های سریع
POPULAR_CODES: list[str] = [
    "US", "GB", "DE", "FR", "NL", "CA", "IT", "ES",
    "TR", "AE", "SE", "PL", "JP", "SG", "AU", "IN",
]


def has_cities(country: str) -> bool:
    return bool(CITIES.get((country or "").upper()))


def cities(country: str) -> list[str]:
    return list(CITIES.get((country or "").upper(), []))


def popular() -> list[tuple[str, str]]:
    """(code, label) برای کشورهای پرکاربرد IPRoyal."""
    return [(c, countries.label(c)) for c in POPULAR_CODES]
