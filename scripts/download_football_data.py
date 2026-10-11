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
import time
import traceback
import urllib.error
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
HEADERS = {"User-Agent": "MatchLambda/1.3 historical-downloader"}
MAX_RESPONSE_BYTES = 8 * 1024 * 1024


def fetch_file(url: str) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        status = getattr(resp, "status", 200)
        if status != 200:
            raise RuntimeError(f"HTTP {status}")
        chunks = []
        total = 0
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_RESPONSE_BYTES:
                raise RuntimeError("response exceeded 8MB")
            chunks.append(chunk)
    raw = b"".join(chunks)
    head = raw.lstrip()[:64].lower()
    if head.startswith(b"<") or head.startswith(b"<!doctype"):
        raise RuntimeError("response was HTML, not CSV")
    return raw


def fetch_file_with_retry(url: str, attempts: int = 3, base_delay: float = 1.0) -> bytes:
    """fetch_file with exponential backoff. Re-raises the last error after attempts."""
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fetch_file(url)
        except Exception as exc:  # noqa: BLE001 - retried, then surfaced to caller
            last_error = exc
            if attempt < attempts:
                delay = base_delay * (2 ** (attempt - 1))
                print(
                    f"  ... attempt {attempt}/{attempts} failed ({exc}); retrying in {delay:.0f}s",
                    file=sys.stderr,
                )
                time.sleep(delay)
    assert last_error is not None
    raise last_error


def decode_csv_content(raw_bytes: bytes) -> str:
    for enc in ["utf-8-sig", "utf-8", "latin-1", "iso-8859-1", "cp1252"]:
        try:
            return raw_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("latin-1", errors="replace")


def parse_csv_rows(text_content: str):
    """
    Parses CSV text into (fieldnames, list of dicts, discarded row count).
    Ignores completely empty rows or trailing metadata notes.
    """
    reader = csv.reader(io.StringIO(text_content))
    rows = list(reader)
    if not rows:
        return [], [], 0

    raw_headers = [h.strip() for h in rows[0]]
    headers = [h for h in raw_headers if h]

    data_rows = []
    discarded = 0
    for r in rows[1:]:
        if not r or not any(r):
            continue
        if len(r) > 0 and r[0].startswith("Key to"):
            break
        if "HomeTeam" not in headers:
            discarded += 1
            continue
        row_dict = {}
        for idx, h in enumerate(headers):
            val = r[idx].strip() if idx < len(r) else ""
            row_dict[h] = val
        if row_dict.get("HomeTeam"):
            data_rows.append(row_dict)
        else:
            discarded += 1

    return headers, data_rows, discarded


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
        "failures": [],
    }

    all_matches_combined = []
    failures = []

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
                raw_bytes = fetch_file_with_retry(url)
                text_content = decode_csv_content(raw_bytes)
                if "HomeTeam" not in text_content.splitlines()[0]:
                    raise RuntimeError("CSV header has no HomeTeam column")
                with open(out_file, "wb") as f:
                    f.write(raw_bytes)

                headers, records, discarded = parse_csv_rows(text_content)
                if discarded:
                    print(f"  ! {season_label}: discarded {discarded} unparsed rows", file=sys.stderr)

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
                # Never pretend success: record the failure, surface the traceback
                # for unexpected errors, and exit non-zero at the end.
                failures.append({
                    "league": short_name,
                    "season": season_label,
                    "url": url,
                    "error": str(e),
                })
                print(f"  ✗ {season_label} ({url}) ERROR: {e}", file=sys.stderr)
                if not isinstance(e, (RuntimeError, urllib.error.URLError, OSError)):
                    traceback.print_exc()

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
    summary_stats["failures"] = failures
    manifest_path = data_dir / "summary.json"
    temporary_manifest = manifest_path.with_suffix(".json.tmp")
    temporary_manifest.write_text(json.dumps(summary_stats, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary_manifest, manifest_path)
    print(f"-> Saved dataset manifest: {manifest_path.name}")

    if failures:
        print(
            f"\n{len(failures)} season download(s) FAILED; the dataset is incomplete.",
            file=sys.stderr,
        )
        for failure in failures:
            print(
                f"  - {failure['league']} {failure['season']}: {failure['error']}",
                file=sys.stderr,
            )
        sys.exit(1)

    print(f"\nAll operations finished successfully! Total matches downloaded: {summary_stats['total_matches']}\n")


if __name__ == "__main__":
    main()
