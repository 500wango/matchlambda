#!/usr/bin/env python3
"""
download_football_data.py
Downloads historical football match results and betting odds from football-data.co.uk
for English Premier League (EPL - E0) and EFL Championship (E1).

Covers recent 10+ seasons (2014/2015 - 2026/2027).
Saves individual season CSVs and combined unified datasets into data/historical/.
"""

import os
import sys
import csv
import json
import urllib.request
import io
from pathlib import Path
from datetime import datetime, timezone

# Seasons configuration: (code, label, start_year, end_year)
SEASONS = [
    ("1415", "2014-2015", 2014, 2015),
    ("1516", "2015-2016", 2015, 2016),
    ("1617", "2016-2017", 2016, 2017),
    ("1718", "2017-2018", 2017, 2018),
    ("1819", "2018-2019", 2018, 2019),
    ("1920", "2019-2020", 2019, 2020),
    ("2021", "2020-2021", 2020, 2021),
    ("2122", "2021-2022", 2021, 2022),
    ("2223", "2022-2023", 2022, 2023),
    ("2324", "2023-2024", 2023, 2024),
    ("2425", "2024-2025", 2024, 2025),
    ("2526", "2025-2026", 2025, 2026),
    ("2627", "2026-2027", 2026, 2027),
]

LEAGUES = {
    "E0": {
        "name": "Premier League",
        "short_name": "EPL",
        "dir_name": "epl",
        "prefix": "E0",
    },
    "E1": {
        "name": "Championship",
        "short_name": "Championship",
        "dir_name": "championship",
        "prefix": "E1",
    },
}

BASE_URL = "https://football-data.co.uk/mmz4281"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def fetch_file(url: str) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def decode_csv_content(raw_bytes: bytes) -> str:
    for enc in ["utf-8-sig", "utf-8", "latin-1", "iso-8859-1", "cp1252"]:
        try:
            return raw_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("latin-1", errors="replace")


def parse_csv_rows(text_content: str):
    """
    Parses CSV text into (fieldnames, list of dicts).
    Ignores completely empty rows or trailing metadata notes.
    """
    reader = csv.reader(io.StringIO(text_content))
    rows = list(reader)
    if not rows:
        return [], []

    raw_headers = [h.strip() for h in rows[0]]
    # Filter valid headers
    headers = [h for h in raw_headers if h]

    data_rows = []
    for r in rows[1:]:
        if not r or not any(r):
            continue
        # Stop if we hit footer notes
        if len(r) > 0 and r[0].startswith("Key to"):
            break
        row_dict = {}
        for idx, h in enumerate(headers):
            val = r[idx].strip() if idx < len(r) else ""
            row_dict[h] = val
        if any(row_dict.values()) and ("HomeTeam" in row_dict and row_dict["HomeTeam"]):
            data_rows.append(row_dict)

    return headers, data_rows


def write_combined_csv(output_path: Path, all_records: list):
    """
    Writes records with a consistent set of columns.
    Ensures core columns come first, followed by bookmaker/stat columns.
    """
    if not all_records:
        return

    # Core order
    core_cols = [
        "Season", "League", "Div", "Date", "Time", "HomeTeam", "AwayTeam",
        "FTHG", "FTAG", "FTR", "HTHG", "HTAG", "HTR", "Referee",
        "HS", "AS", "HST", "AST", "HF", "AF", "HC", "AC", "HY", "AY", "HR", "AR"
    ]

    all_keys = set()
    for rec in all_records:
        all_keys.update(rec.keys())

    extra_cols = sorted([k for k in all_keys if k not in core_cols])
    fieldnames = [c for c in core_cols if c in all_keys] + extra_cols

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for rec in all_records:
            writer.writerow(rec)


def main():
    root_dir = Path(__file__).resolve().parent.parent
    data_dir = root_dir / "data" / "historical"
    data_dir.mkdir(parents=True, exist_ok=True)

    print(f"==================================================")
    print(f"Football-Data.co.uk Historical Downloader (10+ Years)")
    print(f"Target Directory: {data_dir}")
    print(f"==================================================\n")

    summary_stats = {
        "download_time": datetime.now(timezone.utc).isoformat(),
        "source": "https://football-data.co.uk/englandm.php",
        "leagues": {},
        "total_matches": 0,
    }

    all_matches_combined = []

    for div_code, league_info in LEAGUES.items():
        league_name = league_info["name"]
        short_name = league_info["short_name"]
        subdir = data_dir / league_info["dir_name"]
        subdir.mkdir(parents=True, exist_ok=True)

        print(f"[{short_name} - {league_name}] ({div_code})")
        league_matches = []
        season_stats = []

        for code, season_label, start_yr, end_yr in SEASONS:
            url = f"{BASE_URL}/{code}/{div_code}.csv"
            out_filename = f"{league_info['prefix']}_{start_yr}_{end_yr}.csv"
            out_file = subdir / out_filename

            try:
                raw_bytes = fetch_file(url)
                # Save raw file
                with open(out_file, "wb") as f:
                    f.write(raw_bytes)

                text_content = decode_csv_content(raw_bytes)
                headers, records = parse_csv_rows(text_content)

                # Annotate with metadata
                for rec in records:
                    rec["Season"] = season_label
                    rec["League"] = league_name

                league_matches.extend(records)
                all_matches_combined.extend(records)

                file_size_kb = len(raw_bytes) / 1024
                print(f"  ✓ {season_label}: {len(records)} matches, {len(headers)} cols ({file_size_kb:.1f} KB) -> {out_filename}")

                season_stats.append({
                    "season": season_label,
                    "season_code": code,
                    "matches": len(records),
                    "columns": len(headers),
                    "file": str(out_file.relative_to(root_dir)),
                    "file_size_bytes": len(raw_bytes),
                })
            except Exception as e:
                print(f"  ✗ {season_label} ({url}) ERROR: {e}", file=sys.stderr)

        # Write league-specific combined file
        league_combined_file = data_dir / f"{league_info['dir_name']}_combined.csv"
        write_combined_csv(league_combined_file, league_matches)
        print(f"  -> Generated combined {short_name} dataset: {len(league_matches)} total matches -> {league_combined_file.name}\n")

        summary_stats["leagues"][short_name] = {
            "name": league_name,
            "division_code": div_code,
            "total_matches": len(league_matches),
            "seasons_count": len(season_stats),
            "seasons": season_stats,
            "combined_file": str(league_combined_file.relative_to(root_dir)),
        }
        summary_stats["total_matches"] += len(league_matches)

    # Write overall combined dataset
    overall_file = data_dir / "england_10y_combined.csv"
    write_combined_csv(overall_file, all_matches_combined)
    summary_stats["overall_combined_file"] = str(overall_file.relative_to(root_dir))
    print(f"-> Generated master combined dataset: {len(all_matches_combined)} total matches -> {overall_file.name}")

    # Write summary manifest
    manifest_path = data_dir / "summary.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(summary_stats, f, indent=2, ensure_ascii=False)
    print(f"-> Saved dataset manifest: {manifest_path.name}")
    print(f"\nAll operations finished successfully! Total matches downloaded: {summary_stats['total_matches']}\n")


if __name__ == "__main__":
    main()
