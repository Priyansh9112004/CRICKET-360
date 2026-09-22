from pathlib import Path
import pandas as pd

BASE = Path(r"C:\Users\user\OneDrive\Desktop\DATA Analyst\CRICKET_360")
SRC = BASE / "DATA" / "powerbi"
OUT = SRC / "CRICKET_360_POWERBI.xlsx"

FILES = [
    "dim_player.csv",
    "matches.csv",
    "match_summary.csv",
    "player_summary.csv",
    "player_career_by_format.csv",
    "player_by_season.csv",
    "player_vs_team.csv",
    "player_vs_tournament.csv",
    "player_match_batting.csv",
    "player_match_bowling.csv",
    "batting_form_trend.csv",
    "bowling_form_trend.csv",
    "team_summary.csv",
    "team_vs_tournament.csv",
    "head_to_head_summary.csv",
    "tournament_summary.csv",
    "season_summary.csv",
    "venue_summary.csv",
    "format_summary.csv",
]

missing = [f for f in FILES if not (SRC / f).exists()]
if missing:
    print("ERROR - Missing files:")
    for f in missing:
        print(" ", f)
    raise SystemExit(1)

print("Creating:", OUT)
print("This may take a few minutes because the workbook contains many rows.\n")

try:
    writer = pd.ExcelWriter(
        OUT,
        engine="xlsxwriter",
        engine_kwargs={"options": {"strings_to_urls": False}}
    )
except ModuleNotFoundError:
    print("ERROR: xlsxwriter is not installed.")
    print(r'Run: C:\Python312\python.exe -m pip install xlsxwriter')
    raise SystemExit(1)

with writer:
    for i, filename in enumerate(FILES, 1):
        path = SRC / filename
        sheet = path.stem[:31]
        print(f"[{i:02d}/{len(FILES)}] {filename} -> {sheet}")

        df = pd.read_csv(path, low_memory=False)

        # Excel worksheet limit is 1,048,576 rows including header.
        if len(df) > 1_048_575:
            raise ValueError(
                f"{filename} has {len(df):,} rows and cannot fit on one Excel sheet."
            )

        df.to_excel(writer, sheet_name=sheet, index=False)

        ws = writer.sheets[sheet]
        ws.freeze_panes(1, 0)
        ws.autofilter(0, 0, len(df), max(len(df.columns) - 1, 0))

        # Keep headers readable without making the huge workbook slow.
        header_fmt = writer.book.add_format({
            "bold": True,
            "bg_color": "#17365D",
            "font_color": "#FFFFFF",
            "border": 1
        })
        for col_num, value in enumerate(df.columns):
            ws.write(0, col_num, value, header_fmt)

        # Moderate widths based on header names only (fast for large sheets).
        for col_num, col_name in enumerate(df.columns):
            width = min(max(len(str(col_name)) + 2, 12), 28)
            ws.set_column(col_num, col_num, width)

print("\nDONE")
print("Workbook:", OUT)
print("Sheets:", len(FILES))
print("\nIn Power BI:")
print("Get Data -> Excel workbook -> select CRICKET_360_POWERBI.xlsx")
print("Then tick 'Select multiple items' -> Select All -> Load")
