from pathlib import Path
import pandas as pd
import urllib.request
import base64
import mimetypes
import re
import time

# ============================================================
# CRICKET 360 - FINAL TEAM LOGO PIPELINE
# ============================================================

ROOT = Path(__file__).resolve().parent

TEAM_SUMMARY = ROOT / "DATA" / "powerbi" / "team_summary.csv"
OUT = ROOT / "DATA" / "powerbi" / "team_logos_powerbi.csv"

LOGO_DIR = ROOT / "DATA" / "powerbi" / "team_logos"
PENDING_OUT = ROOT / "DATA" / "powerbi" / "team_logos_pending.csv"

WEST_INDIES_FLAG = (
    ROOT / "DATA" / "powerbi" / "west_indies_flag.png"
)

LOGO_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# INTERNATIONAL TEAMS
# ============================================================

INTERNATIONAL_CODES = {
    "Afghanistan": "af",
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
    "England": "gb-eng",
    "Estonia": "ee",
    "Eswatini": "sz",
    "Swaziland": "sz",
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
    "Samoa": "ws",
    "Saudi Arabia": "sa",
    "Scotland": "gb-sct",
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
    "Turks and Caicos Island": "tc",
    "Uganda": "ug",
    "United Arab Emirates": "ae",
    "United States of America": "us",
    "Uzbekistan": "uz",
    "Vanuatu": "vu",
    "Zambia": "zm",
    "Zimbabwe": "zw",
}


SPECIAL_FLAG_URLS = {
    "England": "https://flagcdn.com/w160/gb-eng.png",
    "Scotland": "https://flagcdn.com/w160/gb-sct.png",
}


# ============================================================
# SAFE ALIASES
#
# Only aliases where identity is unambiguous.
# Ambiguous names such as Warriors/Knights/Titans are NOT mapped.
# ============================================================

TEAM_ALIASES = {
    # IPL historical/current naming
    "Royal Challengers Bangalore": "Royal Challengers Bengaluru",
    "Kings XI Punjab": "Punjab Kings",

    # Same franchise spelling variants
    "Rising Pune Supergiants": "Rising Pune Supergiant",

    # Hundred rebrands
    "Manchester Originals": "Manchester Super Giants",
    "London Spirit": "MI London",

    # Sharjah spelling change
    "Sharjah Warriors": "Sharjah Warriorz",

    # Kathmandu spelling variants
    "Kathmandu Gurkhas": "Kathmandu Gorkhas",

    # State-name variants
    "Himachal": "Himachal Pradesh",

    # Auckland / Wellington / Otago common team naming
    "Auckland": "Auckland Aces",
    "Wellington": "Wellington Firebirds",
    "Otago": "Otago Volts",
}


# ============================================================
# HELPERS
# ============================================================

def normalize_name(value):
    value = str(value).strip().lower()
    value = value.replace("&", "and")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def bytes_to_data_uri(data, mime):
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def local_file_to_data_uri(path):
    suffix = path.suffix.lower()

    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
    }

    mime = mime_map.get(
        suffix,
        mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    )

    with open(path, "rb") as f:
        data = f.read()

    return bytes_to_data_uri(data, mime)


def download_png(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    with urllib.request.urlopen(request, timeout=25) as response:
        data = response.read()

    return bytes_to_data_uri(data, "image/png")


def get_flag_url(team, code):
    if team in SPECIAL_FLAG_URLS:
        return SPECIAL_FLAG_URLS[team]

    return f"https://flagcdn.com/w160/{code}.png"


# ============================================================
# INDEX LOCAL LOGOS
# ============================================================

VALID_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".svg",
}

local_logo_index = {}

for file in LOGO_DIR.iterdir():

    if not file.is_file():
        continue

    if file.suffix.lower() not in VALID_EXTENSIONS:
        continue

    key = normalize_name(file.stem)

    if key not in local_logo_index:
        local_logo_index[key] = file


print()
print("=" * 72)
print("CRICKET 360 - FINAL TEAM LOGO BUILD")
print("=" * 72)

print("Local logo files found:", len(local_logo_index))


# ============================================================
# LOAD TEAM SUMMARY
# ============================================================

if not TEAM_SUMMARY.exists():
    raise FileNotFoundError(
        f"Missing file: {TEAM_SUMMARY}"
    )

df = pd.read_csv(
    TEAM_SUMMARY,
    dtype=str
)

if "Team" not in df.columns:
    raise KeyError(
        "Column 'Team' not found in team_summary.csv"
    )

teams = sorted(
    df["Team"]
    .dropna()
    .astype(str)
    .str.strip()
    .unique()
)

print("Teams found:", len(teams))
print()


# ============================================================
# BUILD
# ============================================================

rows = []

for number, team in enumerate(teams, start=1):

    logo_data = ""
    logo_url = ""
    logo_type = ""
    source_name = ""
    status = ""

    team_key = normalize_name(team)

    # --------------------------------------------------------
    # 1. EXACT LOCAL TEAM LOGO
    # --------------------------------------------------------

    if team_key in local_logo_index:

        path = local_logo_index[team_key]

        try:
            logo_data = local_file_to_data_uri(path)
            logo_type = "LOCAL_TEAM_LOGO"
            source_name = path.name
            status = "OK"

        except Exception as error:
            status = "ERROR_LOCAL_" + type(error).__name__

    # --------------------------------------------------------
    # 2. SAFE ALIAS -> LOCAL LOGO
    # --------------------------------------------------------

    elif team in TEAM_ALIASES:

        canonical = TEAM_ALIASES[team]
        canonical_key = normalize_name(canonical)

        if canonical_key in local_logo_index:

            path = local_logo_index[canonical_key]

            try:
                logo_data = local_file_to_data_uri(path)
                logo_type = "LOCAL_ALIAS_LOGO"
                source_name = path.name
                status = "OK"

            except Exception as error:
                status = "ERROR_ALIAS_" + type(error).__name__

        else:
            status = "LOGO_PENDING"

    # --------------------------------------------------------
    # 3. WEST INDIES CUSTOM IMAGE
    # --------------------------------------------------------

    elif team == "West Indies":

        if WEST_INDIES_FLAG.exists():

            try:
                logo_data = local_file_to_data_uri(
                    WEST_INDIES_FLAG
                )

                logo_type = "CUSTOM_WEST_INDIES"
                source_name = WEST_INDIES_FLAG.name
                status = "OK"

            except Exception as error:
                status = "ERROR_WI_" + type(error).__name__

        else:
            status = "WEST_INDIES_FILE_MISSING"

    # --------------------------------------------------------
    # 4. INTERNATIONAL FLAG
    # --------------------------------------------------------

    elif team in INTERNATIONAL_CODES:

        code = INTERNATIONAL_CODES[team]

        logo_url = get_flag_url(
            team,
            code
        )

        try:
            logo_data = download_png(
                logo_url
            )

            logo_type = "INTERNATIONAL_FLAG"
            source_name = "FlagCDN"
            status = "OK"

        except Exception as error:
            status = "ERROR_FLAG_" + type(error).__name__

    # --------------------------------------------------------
    # 5. NO VERIFIED LOGO YET
    # --------------------------------------------------------

    else:

        logo_type = "DOMESTIC_OR_FRANCHISE"
        status = "LOGO_PENDING"

    rows.append(
        {
            "Team": team,
            "logo_data": logo_data,
            "logo_url": logo_url,
            "logo_type": logo_type,
            "source_name": source_name,
            "status": status,
        }
    )

    print(
        f"{number:>3}/{len(teams)}  "
        f"{team:<42} "
        f"{status}"
    )

    if logo_url:
        time.sleep(0.04)


# ============================================================
# SAVE FINAL TABLE
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
# SAVE PENDING LIST
# ============================================================

pending = output[
    output["status"] == "LOGO_PENDING"
].copy()

pending[
    [
        "Team",
        "logo_type",
        "status"
    ]
].to_csv(
    PENDING_OUT,
    index=False,
    encoding="utf-8-sig"
)


# ============================================================
# SUMMARY
# ============================================================

ready = int(
    (output["status"] == "OK").sum()
)

pending_count = int(
    (output["status"] == "LOGO_PENDING").sum()
)

errors = int(
    output["status"]
    .str.startswith("ERROR")
    .sum()
)

international = int(
    (output["logo_type"] == "INTERNATIONAL_FLAG").sum()
)

local_exact = int(
    (output["logo_type"] == "LOCAL_TEAM_LOGO").sum()
)

local_alias = int(
    (output["logo_type"] == "LOCAL_ALIAS_LOGO").sum()
)

custom = int(
    (output["logo_type"] == "CUSTOM_WEST_INDIES").sum()
)


print()
print("=" * 72)
print("DONE")
print("=" * 72)

print("Total Teams:", len(output))
print()
print("International Flags:", international)
print("Exact Local Logos:", local_exact)
print("Alias Local Logos:", local_alias)
print("Custom Logos:", custom)
print()
print("TOTAL READY:", ready)
print("PENDING:", pending_count)
print("ERRORS:", errors)

print()
print("Power BI output:")
print(OUT)

print()
print("Pending-team list:")
print(PENDING_OUT)


# ============================================================
# CHECK LOCAL FILES THAT MATCH NO TEAM
# ============================================================

valid_keys = {
    normalize_name(team)
    for team in teams
}

alias_target_keys = {
    normalize_name(value)
    for value in TEAM_ALIASES.values()
}

unused_files = []

for key, path in local_logo_index.items():

    if (
        key not in valid_keys
        and key not in alias_target_keys
    ):
        unused_files.append(path.name)

if unused_files:

    print()
    print("=" * 72)
    print("LOCAL LOGO FILES NOT MATCHED TO ANY TEAM")
    print("=" * 72)

    for name in sorted(unused_files):
        print(name)


# ============================================================
# ERROR REVIEW
# ============================================================

error_rows = output[
    output["status"].str.startswith("ERROR")
]

if len(error_rows):

    print()
    print("=" * 72)
    print("ERRORS")
    print("=" * 72)

    print(
        error_rows[
            [
                "Team",
                "status"
            ]
        ].to_string(
            index=False
        )
    )

print()