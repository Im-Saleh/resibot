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
# پوشش گسترده‌ی شهرها بر اساس لوکیشن‌های سرویس IPRoyal (۱۹۵+ کشور، هزاران شهر).
# اینجا شهرهای اصلی و پرکاربرد هر کشور فهرست شده‌اند؛ کاربر می‌تواند هر شهر دیگری
# را هم با گزینه‌ی «کد/نام دلخواه» دستی وارد کند (IPRoyal نام آزاد شهر را می‌پذیرد).
CITIES: dict[str, list[str]] = {
    "US": [
        "NewYork", "LosAngeles", "Chicago", "Houston", "Phoenix", "Philadelphia",
        "SanAntonio", "SanDiego", "Dallas", "Austin", "SanJose", "FortWorth",
        "Jacksonville", "Columbus", "Charlotte", "Indianapolis", "SanFrancisco",
        "Seattle", "Denver", "WashingtonDC", "Nashville", "OklahomaCity",
        "ElPaso", "Boston", "Portland", "LasVegas", "Detroit", "Memphis",
        "Louisville", "Baltimore", "Milwaukee", "Albuquerque", "Tucson", "Fresno",
        "Sacramento", "KansasCity", "Mesa", "Atlanta", "Omaha", "ColoradoSprings",
        "Raleigh", "Miami", "VirginiaBeach", "Oakland", "Minneapolis", "Tulsa",
        "Bakersfield", "Wichita", "Arlington", "Tampa", "Orlando", "StLouis",
        "Pittsburgh", "Cincinnati", "Cleveland", "NewOrleans", "Ashburn", "Buffalo",
    ],
    "GB": [
        "London", "Manchester", "Birmingham", "Glasgow", "Liverpool", "Leeds",
        "Sheffield", "Edinburgh", "Bristol", "Cardiff", "Belfast", "Leicester",
        "Coventry", "Nottingham", "Newcastle", "Brighton", "Southampton",
        "Portsmouth", "Reading", "Oxford", "Cambridge", "Aberdeen", "Swansea",
    ],
    "DE": [
        "Berlin", "Munich", "Frankfurt", "Hamburg", "Cologne", "Dusseldorf",
        "Stuttgart", "Leipzig", "Dortmund", "Essen", "Bremen", "Dresden",
        "Hannover", "Nuremberg", "Duisburg", "Bochum", "Wuppertal", "Bielefeld",
        "Bonn", "Mannheim", "Karlsruhe", "Wiesbaden", "Munster", "Augsburg",
    ],
    "FR": [
        "Paris", "Marseille", "Lyon", "Toulouse", "Nice", "Nantes", "Montpellier",
        "Strasbourg", "Bordeaux", "Lille", "Rennes", "Reims", "SaintEtienne",
        "Toulon", "LeHavre", "Grenoble", "Dijon", "Angers", "Nimes", "Cannes",
    ],
    "NL": [
        "Amsterdam", "Rotterdam", "TheHague", "Utrecht", "Eindhoven", "Groningen",
        "Tilburg", "Almere", "Breda", "Nijmegen", "Haarlem", "Arnhem", "Amersfoort",
    ],
    "CA": [
        "Toronto", "Montreal", "Vancouver", "Calgary", "Ottawa", "Edmonton",
        "Winnipeg", "QuebecCity", "Hamilton", "Kitchener", "London", "Victoria",
        "Halifax", "Windsor", "Saskatoon", "Regina", "Mississauga", "Brampton",
    ],
    "IT": [
        "Rome", "Milan", "Naples", "Turin", "Florence", "Bologna", "Venice",
        "Genoa", "Palermo", "Bari", "Catania", "Verona", "Padua", "Trieste",
        "Brescia", "Parma", "Modena", "Cagliari", "Bergamo", "Pisa",
    ],
    "ES": [
        "Madrid", "Barcelona", "Valencia", "Seville", "Malaga", "Zaragoza",
        "Bilbao", "Murcia", "Palma", "LasPalmas", "Alicante", "Cordoba",
        "Valladolid", "Vigo", "Granada", "SanSebastian", "Santander", "Marbella",
    ],
    "TR": [
        "Istanbul", "Ankara", "Izmir", "Bursa", "Antalya", "Adana", "Konya",
        "Gaziantep", "Mersin", "Kayseri", "Eskisehir", "Trabzon", "Samsun",
        "Denizli", "Diyarbakir", "Sanliurfa", "Malatya", "Erzurum",
    ],
    "AE": ["Dubai", "AbuDhabi", "Sharjah", "Ajman", "RasAlKhaimah", "Fujairah", "AlAin"],
    "SE": ["Stockholm", "Gothenburg", "Malmo", "Uppsala", "Vasteras", "Orebro", "Linkoping", "Helsingborg"],
    "PL": [
        "Warsaw", "Krakow", "Wroclaw", "Poznan", "Gdansk", "Lodz", "Szczecin",
        "Bydgoszcz", "Lublin", "Katowice", "Bialystok", "Gdynia", "Czestochowa",
    ],
    "JP": [
        "Tokyo", "Osaka", "Yokohama", "Nagoya", "Sapporo", "Fukuoka", "Kobe",
        "Kyoto", "Kawasaki", "Saitama", "Hiroshima", "Sendai", "Chiba", "Kitakyushu",
    ],
    "SG": ["Singapore"],
    "AU": [
        "Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide", "GoldCoast",
        "Canberra", "Newcastle", "Wollongong", "Hobart", "Geelong", "Darwin", "Cairns",
    ],
    "IN": [
        "Mumbai", "Delhi", "Bangalore", "Chennai", "Hyderabad", "Kolkata", "Pune",
        "Ahmedabad", "Surat", "Jaipur", "Lucknow", "Kanpur", "Nagpur", "Indore",
        "Bhopal", "Visakhapatnam", "Patna", "Vadodara", "Ghaziabad", "Ludhiana",
    ],
    "BR": [
        "SaoPaulo", "RioDeJaneiro", "Brasilia", "Salvador", "Fortaleza",
        "BeloHorizonte", "Manaus", "Curitiba", "Recife", "PortoAlegre", "Belem",
        "Goiania", "Guarulhos", "Campinas", "SaoLuis", "Maceio", "Natal",
    ],
    "RU": [
        "Moscow", "SaintPetersburg", "Novosibirsk", "Yekaterinburg", "Kazan",
        "NizhnyNovgorod", "Chelyabinsk", "Samara", "Omsk", "RostovOnDon", "Ufa",
        "Krasnoyarsk", "Perm", "Voronezh", "Volgograd", "Krasnodar", "Sochi",
    ],
    "CH": ["Zurich", "Geneva", "Bern", "Basel", "Lausanne", "Lucerne", "StGallen", "Lugano", "Winterthur"],
    "BE": ["Brussels", "Antwerp", "Ghent", "Charleroi", "Liege", "Bruges", "Namur", "Leuven"],
    "AT": ["Vienna", "Graz", "Linz", "Salzburg", "Innsbruck", "Klagenfurt", "Villach"],
    "FI": ["Helsinki", "Espoo", "Tampere", "Vantaa", "Oulu", "Turku", "Jyvaskyla", "Lahti"],
    "NO": ["Oslo", "Bergen", "Trondheim", "Stavanger", "Drammen", "Fredrikstad", "Tromso"],
    "DK": ["Copenhagen", "Aarhus", "Odense", "Aalborg", "Esbjerg", "Randers", "Kolding"],
    "IE": ["Dublin", "Cork", "Galway", "Limerick", "Waterford", "Drogheda", "Dundalk"],
    "PT": ["Lisbon", "Porto", "Braga", "Amadora", "Coimbra", "Funchal", "Faro", "Setubal"],
    "KR": ["Seoul", "Busan", "Incheon", "Daegu", "Daejeon", "Gwangju", "Suwon", "Ulsan", "Jeju"],
    "HK": ["HongKong", "Kowloon"],
    "MX": [
        "MexicoCity", "Guadalajara", "Monterrey", "Puebla", "Tijuana", "Leon",
        "Juarez", "Zapopan", "Merida", "Cancun", "Queretaro", "SanLuisPotosi",
    ],
    "ID": ["Jakarta", "Surabaya", "Bandung", "Medan", "Semarang", "Makassar", "Palembang", "Depok", "Denpasar", "Batam"],
    "MY": ["KualaLumpur", "GeorgeTown", "JohorBahru", "Ipoh", "ShahAlam", "PetalingJaya", "KotaKinabalu", "Kuching", "Malacca"],
    "TH": ["Bangkok", "ChiangMai", "Phuket", "Pattaya", "NonthaburiCity", "HatYai", "NakhonRatchasima", "Krabi"],
    "VN": ["Hanoi", "HoChiMinhCity", "DaNang", "HaiPhong", "CanTho", "BienHoa", "NhaTrang", "Hue"],
    "ZA": ["Johannesburg", "CapeTown", "Durban", "Pretoria", "PortElizabeth", "Bloemfontein", "EastLondon", "Soweto"],
    "SA": ["Riyadh", "Jeddah", "Mecca", "Medina", "Dammam", "Khobar", "Taif", "Tabuk", "Abha"],
    "RO": ["Bucharest", "ClujNapoca", "Timisoara", "Iasi", "Constanta", "Craiova", "Brasov", "Galati", "Oradea"],
    "CZ": ["Prague", "Brno", "Ostrava", "Plzen", "Liberec", "Olomouc", "Budejovice"],
    "GR": ["Athens", "Thessaloniki", "Patras", "Heraklion", "Larissa", "Volos", "Ioannina", "Chania"],
    "UA": ["Kyiv", "Kharkiv", "Odesa", "Dnipro", "Lviv", "Zaporizhzhia", "Vinnytsia"],
    "HU": ["Budapest", "Debrecen", "Szeged", "Miskolc", "Pecs", "Gyor", "Nyiregyhaza"],
    "BG": ["Sofia", "Plovdiv", "Varna", "Burgas", "Ruse", "StaraZagora"],
    "SK": ["Bratislava", "Kosice", "Presov", "Zilina", "Nitra", "BanskaBystrica"],
    "HR": ["Zagreb", "Split", "Rijeka", "Osijek", "Zadar", "Dubrovnik"],
    "RS": ["Belgrade", "NoviSad", "Nis", "Kragujevac", "Subotica"],
    "SI": ["Ljubljana", "Maribor", "Celje", "Kranj", "Koper"],
    "LT": ["Vilnius", "Kaunas", "Klaipeda", "Siauliai", "Panevezys"],
    "LV": ["Riga", "Daugavpils", "Liepaja", "Jelgava"],
    "EE": ["Tallinn", "Tartu", "Narva", "Parnu"],
    "IL": ["TelAviv", "Jerusalem", "Haifa", "RishonLeZion", "Netanya", "BeerSheva", "Ashdod"],
    "EG": ["Cairo", "Alexandria", "Giza", "ShubraElKheima", "PortSaid", "Suez", "Luxor", "Aswan"],
    "AR": ["BuenosAires", "Cordoba", "Rosario", "Mendoza", "LaPlata", "Tucuman", "MarDelPlata", "Salta"],
    "CL": ["Santiago", "Valparaiso", "Concepcion", "Antofagasta", "Vina", "Temuco"],
    "CO": ["Bogota", "Medellin", "Cali", "Barranquilla", "Cartagena", "Cucuta", "Bucaramanga"],
    "PE": ["Lima", "Arequipa", "Trujillo", "Chiclayo", "Piura", "Cusco"],
    "PH": ["Manila", "QuezonCity", "Davao", "Cebu", "Makati", "Taguig", "Pasig", "Caloocan"],
    "PK": ["Karachi", "Lahore", "Islamabad", "Rawalpindi", "Faisalabad", "Multan", "Peshawar", "Quetta"],
    "BD": ["Dhaka", "Chittagong", "Khulna", "Rajshahi", "Sylhet", "Comilla"],
    "NG": ["Lagos", "Abuja", "Kano", "Ibadan", "PortHarcourt", "BeninCity", "Kaduna"],
    "KE": ["Nairobi", "Mombasa", "Kisumu", "Nakuru", "Eldoret"],
    "MA": ["Casablanca", "Rabat", "Marrakech", "Fes", "Tangier", "Agadir", "Meknes"],
    "NZ": ["Auckland", "Wellington", "Christchurch", "Hamilton", "Tauranga", "Dunedin"],
    "QA": ["Doha", "AlRayyan", "AlWakrah"],
    "KW": ["KuwaitCity", "Hawalli", "Salmiya", "Jahra"],
    "IQ": ["Baghdad", "Basra", "Mosul", "Erbil", "Najaf", "Karbala", "Sulaymaniyah"],
    "JO": ["Amman", "Zarqa", "Irbid", "Aqaba"],
    "LB": ["Beirut", "Tripoli", "Sidon", "Tyre"],
    "TW": ["Taipei", "Kaohsiung", "Taichung", "Tainan", "Taoyuan", "Hsinchu"],
    "LU": ["LuxembourgCity", "EschSurAlzette", "Differdange"],
    "IS": ["Reykjavik", "Kopavogur", "Hafnarfjordur", "Akureyri"],
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
