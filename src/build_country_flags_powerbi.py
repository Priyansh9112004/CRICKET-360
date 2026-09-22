from pathlib import Path
import pandas as pd
import urllib.request
import base64
import time

# ============================================================
# CRICKET 360 - COUNTRY FLAGS FOR POWER BI
# ============================================================

ROOT = Path(__file__).resolve().parent

DIM_PLAYER = ROOT / "DATA" / "processed" / "dim_player.csv"

# Fallback in case dim_player.csv is stored in powerbi folder
if not DIM_PLAYER.exists():
    DIM_PLAYER = ROOT / "DATA" / "powerbi" / "dim_player.csv"

OUT = ROOT / "DATA" / "powerbi" / "country_flags_powerbi.csv"

WEST_INDIES_FLAG = (
    ROOT
    / "DATA"
    / "powerbi"
    / "west_indies_flag.png"
)


# ============================================================
# COUNTRY -> FLAG CODE
# ============================================================

COUNTRY_CODES = {
    "Afghanistan": "af",
    "Antigua and Barbuda": "ag",
    "Argentina": "ar",
    "Australia": "au",
    "Austria": "at",
    "Bahamas": "bs",
    "Bahrain": "bh",
    "Bangladesh": "bd",
    "Barbados": "bb",
    "Belgium": "be",
    "Belize": "bz",
    "Bermuda": "bm",
    "Bhutan": "bt",
    "Botswana": "bw",
    "Brazil": "br",
    "Bulgaria": "bg",
    "Cambodia": "kh",
    "Cameroon": "cm",
    "Canada": "ca",
    "Cayman Islands": "ky",
    "Chile": "cl",
    "China": "cn",
    "Cook Islands": "ck",
    "Costa Rica": "cr",
    "Croatia": "hr",
    "Cyprus": "cy",
    "Czech Republic": "cz",
    "Denmark": "dk",
    "Dominica": "dm",

    # UK cricket nations
    "England": "gb-eng",
    "Scotland": "gb-sct",

    "Estonia": "ee",
    "Eswatini": "sz",
    "Fiji": "fj",
    "Finland": "fi",
    "France": "fr",
    "Gambia": "gm",
    "Germany": "de",
    "Ghana": "gh",
    "Gibraltar": "gi",
    "Greece": "gr",
    "Guernsey": "gg",
    "Guyana": "gy",
    "Hong Kong": "hk",
    "Hungary": "hu",
    "India": "in",
    "Indonesia": "id",
    "Iran": "ir",
    "Ireland": "ie",
    "Isle of Man": "im",
    "Israel": "il",
    "Italy": "it",
    "Ivory Coast": "ci",
    "Jamaica": "jm",
    "Japan": "jp",
    "Jersey": "je",
    "Kenya": "ke",
    "Kuwait": "kw",
    "Lesotho": "ls",
    "Luxembourg": "lu",
    "Malawi": "mw",
    "Malaysia": "my",
    "Maldives": "mv",
    "Mali": "ml",
    "Malta": "mt",
    "Mexico": "mx",
    "Mongolia": "mn",
    "Mozambique": "mz",
    "Myanmar": "mm",
    "Namibia": "na",
    "Nepal": "np",
    "Netherlands": "nl",
    "New Zealand": "nz",
    "Nigeria": "ng",
    "Norway": "no",
    "Oman": "om",
    "Pakistan": "pk",
    "Panama": "pa",
    "Papua New Guinea": "pg",
    "Peru": "pe",
    "Philippines": "ph",
    "Portugal": "pt",
    "Qatar": "qa",
    "Romania": "ro",
    "Rwanda": "rw",
    "Saint Lucia": "lc",
    "Saint Vincent and the Grenadines": "vc",
    "Samoa": "ws",
    "Saudi Arabia": "sa",
    "Serbia": "rs",
    "Seychelles": "sc",
    "Sierra Leone": "sl",
    "Singapore": "sg",
    "Slovenia": "si",
    "South Africa": "za",
    "South Korea": "kr",
    "Spain": "es",
    "Sri Lanka": "lk",
    "St Helena": "sh",
    "Suriname": "sr",
    "Sweden": "se",
    "Switzerland": "ch",
    "Tanzania": "tz",
    "Thailand": "th",
    "Timor-Leste": "tl",
    "Trinidad and Tobago": "tt",
    "Turkey": "tr",

    # Both versions supported
    "Turks and Caicos": "tc",
    "Turks and Caicos Island": "tc",

    "Uganda": "ug",
    "United Arab Emirates": "ae",
    "United Kingdom": "gb",
    "United States": "us",
    "Uzbekistan": "uz",
    "Vanuatu": "vu",
    "Zambia": "zm",
    "Zimbabwe": "zw",

    # Handled separately
    "West Indies": None,
    "Not Available": None,
}


# ============================================================
# SPECIAL FLAG URLS
# ============================================================

SPECIAL_URLS = {
    "England": "https://flagcdn.com/w160/gb-eng.png",
    "Scotland": "https://flagcdn.com/w160/gb-sct.png",
}


# ============================================================
# FUNCTIONS
# ============================================================

def get_flag_url(country, code):
    if country in SPECIAL_URLS:
        return SPECIAL_URLS[country]

    if not code:
        return ""

    return f"https://flagcdn.com/w160/{code}.png"


def bytes_to_data_uri(data):
    encoded = base64.b64encode(data).decode("ascii")
    return "data:image/png;base64," + encoded


def download_flag(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=20
    ) as response:
        data = response.read()

    return bytes_to_data_uri(data)


def load_local_flag(path):
    with open(path, "rb") as file:
        data = file.read()

    return bytes_to_data_uri(data)


# ============================================================
# LOAD PLAYER DATA
# ============================================================

if not DIM_PLAYER.exists():
    raise FileNotFoundError(
        f"dim_player.csv not found: {DIM_PLAYER}"
    )

df = pd.read_csv(
    DIM_PLAYER,
    dtype=str
)

if "country" not in df.columns:
    raise KeyError(
        "Column 'country' not found in dim_player.csv"
    )


# ============================================================
# GET UNIQUE COUNTRIES
# ============================================================

countries = (
    df["country"]
    .dropna()
    .astype(str)
    .str.strip()
)

countries = sorted(
    country
    for country in countries.unique()
    if country
)

print()
print("CRICKET 360 - COUNTRY FLAG BUILD")
print("----------------------------------")
print("Countries found:", len(countries))
print()


# ============================================================
# BUILD FLAG TABLE
# ============================================================

rows = []

for number, country in enumerate(countries, start=1):

    code = COUNTRY_CODES.get(country)

    flag_url = ""
    flag_data = ""
    status = ""

    # --------------------------------------------------------
    # WEST INDIES - USE LOCAL CUSTOM IMAGE
    # --------------------------------------------------------

    if country == "West Indies":

        if WEST_INDIES_FLAG.exists():

            try:
                flag_data = load_local_flag(
                    WEST_INDIES_FLAG
                )

                status = "OK"

            except Exception as error:
                status = (
                    "ERROR: "
                    + type(error).__name__
                )

        else:
            status = "WEST_INDIES_FLAG_FILE_MISSING"

    # --------------------------------------------------------
    # NOT AVAILABLE
    # --------------------------------------------------------

    elif country == "Not Available":

        status = "NO_FLAG"

    # --------------------------------------------------------
    # COUNTRY NOT IN MAPPING
    # --------------------------------------------------------

    elif country not in COUNTRY_CODES:

        status = "UNMAPPED"

    # --------------------------------------------------------
    # NORMAL COUNTRY FLAG
    # --------------------------------------------------------

    else:

        flag_url = get_flag_url(
            country,
            code
        )

        if not flag_url:

            status = "NO_FLAG"

        else:

            try:
                flag_data = download_flag(
                    flag_url
                )

                status = "OK"

            except Exception as error:
                status = (
                    "ERROR: "
                    + type(error).__name__
                )

    # --------------------------------------------------------
    # ADD OUTPUT ROW
    # --------------------------------------------------------

    rows.append(
        {
            "country": country,
            "country_code": code or "",
            "flag_url": flag_url,
            "flag_data": flag_data,
            "status": status,
        }
    )

    print(
        f"{number:>3}/{len(countries)}  "
        f"{country:<35}  "
        f"{status}"
    )

    time.sleep(0.05)


# ============================================================
# SAVE CSV
# ============================================================

output = pd.DataFrame(rows)

OUT.parent.mkdir(
    parents=True,
    exist_ok=True
)

output.to_csv(
    OUT,
    index=False,
    encoding="utf-8-sig"
)


# ============================================================
# SUMMARY
# ============================================================

flags_ok = (
    output["status"] == "OK"
).sum()

unmapped = (
    output["status"] == "UNMAPPED"
).sum()

errors = (
    output["status"]
    .str.startswith("ERROR")
).sum()


print()
print("=" * 60)
print("DONE")
print("=" * 60)

print("Countries:", len(output))
print("Flags OK:", flags_ok)
print("Unmapped:", unmapped)
print("Errors:", errors)
print("Output:", OUT)

print()


# ============================================================
# REVIEW NON-OK ROWS
# ============================================================

problem = output[
    output["status"] != "OK"
][
    [
        "country",
        "status"
    ]
]

if len(problem):

    print("Needs review:")
    print(
        problem.to_string(
            index=False
        )
    )

else:

    print("All countries have flags.")

print()