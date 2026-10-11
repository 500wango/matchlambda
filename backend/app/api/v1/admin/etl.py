import io
import csv
import hashlib
import math
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict, Field, field_validator
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
import httpx

from app.core.database import get_db
from app.models import League, Team, TeamAlias, Match, OddsSnapshot, User
from app.api.deps import require_admin_user
from app.math.shin import calculate_shin_probabilities
from app.services.settings_service import record_audit

router = APIRouter()

LEAGUE_CODE_MAP = {
    "E0": ("EPL", "England"),
    "E1": ("CHAMPIONSHIP", "England"),
    "SP1": ("LA_LIGA", "Spain"),
    "I1": ("SERIE_A", "Italy"),
    "D1": ("BUNDESLIGA", "Germany"),
    "F1": ("LIGUE_1", "France"),
    "N1": ("EREDIVISIE", "Netherlands"),
    "P1": ("PRIMEIRA_LIGA", "Portugal"),
    "B1": ("BEL", "Belgium"),
    "AUT": ("AUSTRIAN_BUNDESLIGA", "Austria"),
    "DNK": ("SUPERLIGA", "Denmark"),
    "NOR": ("ELITESERIEN", "Norway"),
    "SWE": ("ALLSVENSKAN", "Sweden"),
}

FOOTBALL_DATA_BASE_URL = "https://football-data.co.uk/mmz4281"
FOOTBALL_DATA_HOST = "football-data.co.uk"
MAX_CSV_BYTES = 5_000_000

LEAGUE_TIMEZONES = {
    "EPL": "Europe/London",
    "CHAMPIONSHIP": "Europe/London",
    "LA_LIGA": "Europe/Madrid",
    "SERIE_A": "Europe/Rome",
    "BUNDESLIGA": "Europe/Berlin",
    "LIGUE_1": "Europe/Paris",
    "EREDIVISIE": "Europe/Amsterdam",
    "PRIMEIRA_LIGA": "Europe/Lisbon",
    "BEL": "Europe/Brussels",
    "AUSTRIAN_BUNDESLIGA": "Europe/Vienna",
    "SUPERLIGA": "Europe/Copenhagen",
    "ELITESERIEN": "Europe/Oslo",
    "ALLSVENSKAN": "Europe/Stockholm",
    "MLS": "America/New_York",
    "BRASILEIRAO": "America/Sao_Paulo",
}


class SyncRemoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    league_code: str = "E0"
    season: str = Field(default="2627", pattern=r"^\d{4}$")
    auto_train: bool = True


class CommitCsvRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    csv_content: str = Field(max_length=5_000_000)
    league_id: str
    season: Optional[str] = None
    alias_mappings: Dict[str, Optional[str]] = {}
    auto_train: bool = True


class AddAliasRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_name: str = Field(default="football_data", min_length=1, max_length=32)
    external_name: str = Field(min_length=1, max_length=128)
    country: str = Field(min_length=1, max_length=64)
    team_id: str = Field(min_length=1, max_length=64)

    @field_validator("source_name", "external_name", "country", "team_id", mode="before")
    @classmethod
    def strip_fields(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value


def _normalize_new_league_csv(text_content: str, season_code: str) -> str:
    """Normalizes football-data.co.uk new/ format (AUT, DNK, NOR, SWE) into standard mmz4281 format."""
    reader = csv.reader(io.StringIO(text_content))
    rows = list(reader)
    if not rows:
        return text_content
    raw_headers = [h.strip() for h in rows[0]]
    if "Home" not in raw_headers:
        return text_content

    start_year = int("20" + season_code[:2]) if len(season_code) >= 2 else 2026
    end_year = int("20" + season_code[2:]) if len(season_code) == 4 else start_year + 1
    candidate_seasons = {
        f"{start_year}/{end_year}",
        f"{start_year}-{end_year}",
        f"{start_year}",
        season_code,
    }

    header_indices = {h: idx for idx, h in enumerate(raw_headers)}
    target_headers = [
        "Div", "Date", "Time", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR",
        "PSH", "PSD", "PSA", "MaxH", "MaxD", "MaxA", "AvgH", "AvgD", "AvgA",
        "B365H", "B365D", "B365A", "Season"
    ]
    output_rows = [",".join(target_headers)]

    def _get(r, name):
        idx = header_indices.get(name)
        return r[idx].strip() if idx is not None and idx < len(r) else ""

    matched_count = 0
    for r in rows[1:]:
        if not r or not any(r):
            continue
        row_season = _get(r, "Season")
        if candidate_seasons and row_season not in candidate_seasons:
            continue
        home = _get(r, "Home")
        away = _get(r, "Away")
        if not home or not away:
            continue

        matched_count += 1
        h_str = f'"{home}"' if "," in home else home
        a_str = f'"{away}"' if "," in away else away
        out = [
            "",
            _get(r, "Date"),
            _get(r, "Time"),
            h_str,
            a_str,
            _get(r, "HG"),
            _get(r, "AG"),
            _get(r, "Res"),
            _get(r, "PSCH") or _get(r, "PH") or _get(r, "PSH"),
            _get(r, "PSCD") or _get(r, "PD") or _get(r, "PSD"),
            _get(r, "PSCA") or _get(r, "PA") or _get(r, "PSA"),
            _get(r, "MaxCH") or _get(r, "MaxH"),
            _get(r, "MaxCD") or _get(r, "MaxD"),
            _get(r, "MaxCA") or _get(r, "MaxA"),
            _get(r, "AvgCH") or _get(r, "AvgH"),
            _get(r, "AvgCD") or _get(r, "AvgD"),
            _get(r, "AvgCA") or _get(r, "AvgA"),
            _get(r, "B365CH") or _get(r, "B365H"),
            _get(r, "B365CD") or _get(r, "B365D"),
            _get(r, "B365CA") or _get(r, "B365A"),
            row_season,
        ]
        output_rows.append(",".join(out))

    if matched_count == 0:
        return text_content
    return "\n".join(output_rows)


async def _download_football_data_csv(season: str, league_code: str) -> str:
    """Fetch one football-data.co.uk CSV. Redirects and other hosts are refused."""
    if not (season.isdigit() and len(season) == 4):
        raise HTTPException(status_code=400, detail="Season must be four digits.")
    if league_code not in LEAGUE_CODE_MAP or "/" in league_code or ".." in league_code:
        raise HTTPException(status_code=400, detail="Unsupported league code.")
    if league_code in {"AUT", "DNK", "NOR", "SWE"}:
        url = f"https://{FOOTBALL_DATA_HOST}/new/{league_code}.csv"
    else:
        url = f"{FOOTBALL_DATA_BASE_URL}/{season}/{league_code}.csv"
    parsed = urlparse(url)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() != FOOTBALL_DATA_HOST:
        raise HTTPException(status_code=400, detail="Remote host is not allowed.")
    if parsed.username or parsed.password or ".." in parsed.path:
        raise HTTPException(status_code=400, detail="Remote path is not allowed.")
    timeout = httpx.Timeout(15.0, connect=5.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            async with client.stream("GET", url, headers={"User-Agent": "MatchLambda/1.3"}) as resp:
                if resp.status_code in {301, 302, 303, 307, 308}:
                    raise HTTPException(status_code=502, detail="Remote host returned a redirect.")
                if resp.status_code != 200:
                    raise HTTPException(status_code=502, detail=f"Remote host returned HTTP {resp.status_code}.")
                chunks = []
                total = 0
                async for chunk in resp.aiter_bytes():
                    total += len(chunk)
                    if total > MAX_CSV_BYTES:
                        raise HTTPException(status_code=413, detail="Remote CSV exceeds 5MB.")
                    chunks.append(chunk)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to fetch the remote CSV.")
    raw = b"".join(chunks)
    head = raw.lstrip()[:80].lower()
    if head.startswith(b"<") or b"<html" in head or b"<!doctype" in head:
        raise HTTPException(status_code=502, detail="Remote response was not a CSV.")
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        decoded = raw.decode("latin-1", errors="replace")

    if league_code in {"AUT", "DNK", "NOR", "SWE"}:
        return _normalize_new_league_csv(decoded, season)
    return decoded


def _parse_csv_text(text: str) -> Tuple[List[str], List[Dict[str, str]]]:
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return [], []

    raw_headers = [h.strip() for h in rows[0]]
    headers = [h for h in raw_headers if h]

    records = []
    for r in rows[1:]:
        if not r or not any(r):
            continue
        if len(r) > 0 and r[0].startswith("Key to"):
            break
        row_dict = {}
        for idx, h in enumerate(headers):
            val = r[idx].strip() if idx < len(r) else ""
            row_dict[h] = val
        if "HomeTeam" in row_dict and row_dict["HomeTeam"]:
            records.append(row_dict)

    return headers, records


def _parse_match_date(date_str: str, time_str: Optional[str] = None, tz_name: str = "UTC") -> Optional[datetime]:
    if not date_str:
        return None
    time_part = time_str.strip() if time_str else "15:00"
    if len(time_part) == 4 and ":" not in time_part:
        time_part = f"{time_part[:2]}:{time_part[2:]}"
    elif len(time_part) == 5 and ":" in time_part:
        pass
    else:
        time_part = "15:00"

    formats = [
        ("%d/%m/%Y %H:%M", True),
        ("%d/%m/%y %H:%M", True),
        ("%Y-%m-%d %H:%M", True),
        ("%d/%m/%Y", False),
        ("%d/%m/%y", False),
        ("%Y-%m-%d", False),
    ]

    for fmt, has_time in formats:
        try:
            target_str = f"{date_str.strip()} {time_part}" if has_time else date_str.strip()
            dt = datetime.strptime(target_str, fmt)
            try:
                tz = ZoneInfo(tz_name)
            except Exception:
                tz = timezone.utc
            return dt.replace(tzinfo=tz)
        except ValueError:
            continue
    return None


def _name_tokens(text: str) -> set:
    cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in text)
    stop = {"fc", "afc", "cf", "sc", "ac", "the"}
    return {tok for tok in cleaned.split() if tok and tok not in stop}


def _rank_team_candidates(raw_name: str, teams: List[Team]) -> List[Dict[str, Any]]:
    """Token-overlap candidates only. Nothing here is preselected."""
    raw_tokens = _name_tokens(raw_name)
    if not raw_tokens:
        return []
    ranked = []
    for team in teams:
        name_tokens = _name_tokens(team.canonical_name)
        overlap = raw_tokens & name_tokens
        if not overlap:
            continue
        precision = len(overlap) / len(name_tokens)
        recall = len(overlap) / len(raw_tokens)
        score = round(0.5 * precision + 0.5 * recall, 3)
        if score < 0.5:
            continue
        ranked.append({
            "team_id": team.id,
            "team_name": team.canonical_name,
            "score": score,
        })
    ranked.sort(key=lambda item: (-item["score"], item["team_id"]))
    return ranked[:8]


def _build_match_id(league_id: str, date_tag: str, home_id: str, away_id: str) -> str:
    raw = f"{league_id}_{date_tag}_{home_id}_vs_{away_id}"
    if len(raw) <= 64:
        return raw
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{league_id}_{date_tag}_{digest}"[:64]


def _positive_odds(raw: Optional[str]) -> Optional[float]:
    if raw is None or str(raw).strip() == "":
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or value <= 1.0:
        return None
    return value


def _choose_odds(row: Dict[str, str]) -> Tuple[Optional[str], Optional[List[float]]]:
    columns = (
        ("pinnacle", ("PSH", "PSD", "PSA")),
        ("bet365", ("B365H", "B365D", "B365A")),
        ("market_max", ("MaxH", "MaxD", "MaxA")),
        ("market_average", ("AvgH", "AvgD", "AvgA")),
    )
    for bookmaker, keys in columns:
        values = [_positive_odds(row.get(key)) for key in keys]
        if all(values):
            return bookmaker, values
    return None, None


async def _build_team_lookup(db: AsyncSession) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Builds lookup caches:
    1. canonical_lookup: lower(canonical_name) or lower(id) -> team_id
    2. alias_lookup: lower(external_name) -> team_id
    """
    teams_stmt = select(Team)
    teams = (await db.execute(teams_stmt)).scalars().all()
    canonical_lookup = {}
    for t in teams:
        canonical_lookup[t.id.lower()] = t.id
        canonical_lookup[t.canonical_name.lower()] = t.id

    alias_stmt = select(TeamAlias)
    aliases = (await db.execute(alias_stmt)).scalars().all()
    alias_lookup = {}
    for a in aliases:
        alias_lookup[a.external_name.lower()] = a.team_id

    return canonical_lookup, alias_lookup


def _resolve_team_id(
    raw_name: str,
    canonical_lookup: Dict[str, str],
    alias_lookup: Dict[str, str],
    custom_mappings: Dict[str, str],
) -> Optional[str]:
    if not raw_name:
        return None
    raw_clean = raw_name.strip()
    raw_lower = raw_clean.lower()

    if raw_clean in custom_mappings:
        return custom_mappings[raw_clean]
    if raw_lower in custom_mappings:
        return custom_mappings[raw_lower]
    if raw_lower in alias_lookup:
        return alias_lookup[raw_lower]
    if raw_lower in canonical_lookup:
        return canonical_lookup[raw_lower]

    # Simple normalization attempt (e.g. remove FC, AFC, United)
    norm = raw_lower.replace(" fc", "").replace(" afc", "").strip()
    if norm in canonical_lookup:
        return canonical_lookup[norm]
    if norm in alias_lookup:
        return alias_lookup[norm]

    return None


@router.get("/leagues")
async def get_leagues_status(
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns all configured leagues with total matches, finished count, and team counts.
    """
    leagues_stmt = select(League).order_by(League.name.asc())
    leagues = (await db.execute(leagues_stmt)).scalars().all()

    result = []
    for l in leagues:
        # Match count
        match_stmt = select(
            func.count(Match.id),
            func.count(func.nullif(Match.status != "FINISHED", True)),
            func.max(Match.match_date),
        ).where(Match.league_id == l.id)
        m_total, m_finished, latest_dt = (await db.execute(match_stmt)).one()

        result.append({
            "id": l.id,
            "name": l.name,
            "country": l.country,
            "active": l.active,
            "total_matches": m_total or 0,
            "finished_matches": m_finished or 0,
            "latest_match_date": latest_dt.isoformat() if latest_dt else None,
        })

    return {
        "leagues": result,
        "supported_remote_codes": LEAGUE_CODE_MAP,
    }


@router.get("/teams")
async def get_teams_catalog(
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns list of canonical teams and existing aliases for UI mapping helpers.
    """
    teams_stmt = select(Team).order_by(Team.canonical_name.asc())
    teams = (await db.execute(teams_stmt)).scalars().all()

    aliases_stmt = select(TeamAlias).order_by(TeamAlias.external_name.asc())
    aliases = (await db.execute(aliases_stmt)).scalars().all()

    alias_map = {}
    for a in aliases:
        alias_map.setdefault(a.team_id, []).append({
            "external_name": a.external_name,
            "source": a.source_name,
        })

    return [
        {
            "id": t.id,
            "canonical_name": t.canonical_name,
            "country": t.country,
            "aliases": alias_map.get(t.id, []),
        }
        for t in teams
    ]


@router.post("/aliases")
async def create_team_alias(
    req: AddAliasRequest,
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Manually creates a new team alias.
    """
    team = await db.get(Team, req.team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Target team not found")

    alias = TeamAlias(
        source_name=req.source_name,
        external_name=req.external_name,
        country=req.country,
        team_id=team.id,
    )
    db.add(alias)
    try:
        await record_audit(
            db,
            admin_email=admin.email,
            action="CREATE_ALIAS",
            target=req.external_name,
            details={
                "team_id": team.id,
                "canonical_name": team.canonical_name,
                "source": req.source_name,
                "country": req.country,
            },
        )
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Alias already exists.")
    # record_audit flushes only; the alias and its audit row commit together.
    await db.commit()
    return {"status": "SUCCESS", "message": f"Alias '{req.external_name}' bound to team '{team.canonical_name}'."}


@router.post("/upload-csv/preview")
async def preview_csv_import(
    file: UploadFile = File(...),
    league_id: str = Form("EPL"),
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Parses an uploaded CSV file, checks against DB for unknown teams,
    and returns a dry-run preview report without writing changes.
    """
    raw_bytes = await file.read(MAX_CSV_BYTES + 1)
    if len(raw_bytes) > MAX_CSV_BYTES:
        raise HTTPException(status_code=413, detail="CSV exceeds 5MB.")
    filename = (file.filename or "").lower()
    content_type = (file.content_type or "").lower()
    looks_like_csv = filename.endswith(".csv") or "csv" in content_type or content_type.startswith("text/")
    if filename and not looks_like_csv:
        raise HTTPException(status_code=415, detail="Upload must be a CSV file.")
    try:
        text_content = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text_content = raw_bytes.decode("latin-1", errors="replace")

    headers, records = _parse_csv_text(text_content)
    if not records:
        raise HTTPException(status_code=400, detail="CSV file contains no valid match rows.")

    canonical_lookup, alias_lookup = await _build_team_lookup(db)
    teams = (await db.execute(select(Team))).scalars().all()

    unknown_teams_set = set()
    sample_matches = []
    finished_count = 0

    for idx, r in enumerate(records):
        h_raw = r.get("HomeTeam", "").strip()
        a_raw = r.get("AwayTeam", "").strip()
        h_id = _resolve_team_id(h_raw, canonical_lookup, alias_lookup, {})
        a_id = _resolve_team_id(a_raw, canonical_lookup, alias_lookup, {})

        if not h_id and h_raw:
            unknown_teams_set.add(h_raw)
        if not a_id and a_raw:
            unknown_teams_set.add(a_raw)

        fthg = r.get("FTHG")
        ftag = r.get("FTAG")
        is_finished = bool(fthg is not None and ftag is not None and fthg != "" and ftag != "")
        if is_finished:
            finished_count += 1

        if idx < 5:
            sample_matches.append({
                "date": r.get("Date"),
                "home_raw": h_raw,
                "away_raw": a_raw,
                "home_id": h_id,
                "away_id": a_id,
                "fthg": fthg,
                "ftag": ftag,
                "status": "FINISHED" if is_finished else "SCHEDULED",
            })

    suggestions = {unk: _rank_team_candidates(unk, teams) for unk in unknown_teams_set}

    return {
        "status": "PREVIEW",
        "total_rows": len(records),
        "finished_matches": finished_count,
        "scheduled_matches": len(records) - finished_count,
        "unknown_teams": sorted(list(unknown_teams_set)),
        "suggested_mappings": suggestions,
        "sample_matches": sample_matches,
        "raw_csv_length": len(text_content),
        "csv_content": text_content,
    }


@router.post("/upload-csv/commit")
async def commit_csv_import(
    req: CommitCsvRequest,
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Commits match records from CSV into DB, applies alias mappings,
    inserts/updates matches and odds snapshots, and optionally re-fits Dixon-Coles.
    """
    league = await db.get(League, req.league_id)
    if not league:
        raise HTTPException(status_code=404, detail=f"League '{req.league_id}' not found.")

    headers, records = _parse_csv_text(req.csv_content)
    if not records:
        raise HTTPException(status_code=400, detail="CSV content is empty.")

    aliases_created = 0
    clean_mappings: Dict[str, str] = {}
    for ext_name, target_id in (req.alias_mappings or {}).items():
        if target_id is None or not str(target_id).strip() or not str(ext_name).strip():
            continue
        target_text = str(target_id).strip()
        external_text = str(ext_name).strip()
        if len(target_text) > 64 or len(external_text) > 128:
            raise HTTPException(status_code=422, detail=f"Alias mapping '{ext_name}' exceeds the column length.")
        team = await db.get(Team, target_text)
        if not team:
            raise HTTPException(status_code=422, detail=f"Unknown team_id '{target_id}' for alias '{ext_name}'.")
        clean_mappings[str(ext_name).strip()] = team.id

    for ext_name, target_id in clean_mappings.items():
        stmt = select(TeamAlias).where(
            TeamAlias.external_name == ext_name,
            TeamAlias.source_name == "football_data",
        )
        existing = (await db.execute(stmt)).scalars().first()
        if not existing:
            db.add(TeamAlias(
                source_name="football_data",
                external_name=ext_name,
                country=league.country,
                team_id=target_id,
            ))
            aliases_created += 1

    canonical_lookup, alias_lookup = await _build_team_lookup(db)
    tz_name = LEAGUE_TIMEZONES.get(req.league_id, "UTC")

    inserted_matches = 0
    updated_matches = 0
    skipped_matches = 0
    now = datetime.now(timezone.utc)
    prepared_rows = []

    for r in records:
        h_raw = r.get("HomeTeam", "").strip()
        a_raw = r.get("AwayTeam", "").strip()
        h_id = _resolve_team_id(h_raw, canonical_lookup, alias_lookup, clean_mappings)
        a_id = _resolve_team_id(a_raw, canonical_lookup, alias_lookup, clean_mappings)

        if not h_id or not a_id:
            skipped_matches += 1
            continue

        match_date = _parse_match_date(r.get("Date", ""), r.get("Time", ""), tz_name)
        if not match_date:
            skipped_matches += 1
            continue

        season = req.season or r.get("Season") or f"{match_date.year}"
        fthg_raw = r.get("FTHG")
        ftag_raw = r.get("FTAG")
        is_finished = bool(fthg_raw is not None and ftag_raw is not None and fthg_raw != "" and ftag_raw != "")

        home_score = None
        away_score = None
        if is_finished:
            try:
                home_score = int(str(fthg_raw).strip())
                away_score = int(str(ftag_raw).strip())
            except ValueError:
                skipped_matches += 1
                continue
        m_status = "FINISHED" if is_finished else "SCHEDULED"
        result_available_at = match_date + timedelta(hours=2) if is_finished else None

        date_tag = match_date.strftime("%Y%m%d")
        match_id = _build_match_id(req.league_id, date_tag, h_id, a_id)
        bookmaker_name, prices = _choose_odds(r)
        prepared_rows.append({
            "match_id": match_id,
            "season": season,
            "match_date": match_date,
            "h_id": h_id,
            "a_id": a_id,
            "status": m_status,
            "home_score": home_score,
            "away_score": away_score,
            "result_available_at": result_available_at,
            "bookmaker_name": bookmaker_name,
            "prices": prices,
        })

    match_ids = list({row["match_id"] for row in prepared_rows})
    match_cache: Dict[str, Match] = {}
    snap_cache: Dict[Tuple[str, str, datetime], OddsSnapshot] = {}
    if match_ids:
        loaded = (await db.execute(select(Match).where(Match.id.in_(match_ids)))).scalars().all()
        match_cache = {match.id: match for match in loaded}
        snaps = (await db.execute(
            select(OddsSnapshot).where(
                OddsSnapshot.match_id.in_(match_ids),
                OddsSnapshot.source_name == "football_data",
            )
        )).scalars().all()
        snap_cache = {(snap.match_id, snap.bookmaker, snap.quote_at): snap for snap in snaps}

    for row in prepared_rows:
        match_id = row["match_id"]
        match_date = row["match_date"]
        home_score = row["home_score"]
        away_score = row["away_score"]
        m_status = row["status"]
        result_available_at = row["result_available_at"]
        existing_match = match_cache.get(match_id)
        if existing_match:
            existing_match.home_score = home_score
            existing_match.away_score = away_score
            existing_match.status = m_status
            existing_match.result_available_at = result_available_at
            existing_match.updated_at = now
            updated_matches += 1
        else:
            match_obj = Match(
                id=match_id,
                league_id=req.league_id,
                season=row["season"],
                match_date=match_date,
                home_team_id=row["h_id"],
                away_team_id=row["a_id"],
                status=m_status,
                home_score=home_score,
                away_score=away_score,
                result_available_at=result_available_at,
                updated_at=now,
            )
            db.add(match_obj)
            match_cache[match_id] = match_obj
            inserted_matches += 1

        bookmaker_name = row["bookmaker_name"]
        prices = row["prices"]
        if bookmaker_name and prices:
            ps_h, ps_d, ps_a = prices
            quote_time = match_date - timedelta(hours=2)
            try:
                probs, _, method = calculate_shin_probabilities([ps_h, ps_d, ps_a])
            except Exception:
                inv = [1.0 / ps_h, 1.0 / ps_d, 1.0 / ps_a]
                s = sum(inv)
                probs = [p / s for p in inv]
                method = "MULTIPLICATIVE"

            snap_key = (match_id, bookmaker_name, quote_time)
            existing_snap = snap_cache.get(snap_key)

            if existing_snap:
                existing_snap.home_odds = ps_h
                existing_snap.draw_odds = ps_d
                existing_snap.away_odds = ps_a
                existing_snap.dejuice_method = method
                existing_snap.implied_prob_home = probs[0]
                existing_snap.implied_prob_draw = probs[1]
                existing_snap.implied_prob_away = probs[2]
            else:
                odds_snap = OddsSnapshot(
                    match_id=match_id,
                    source_name="football_data",
                    bookmaker=bookmaker_name,
                    quote_at=quote_time,
                    recorded_at=quote_time + timedelta(seconds=15),
                    home_odds=ps_h,
                    draw_odds=ps_d,
                    away_odds=ps_a,
                    dejuice_method=method,
                    implied_prob_home=probs[0],
                    implied_prob_draw=probs[1],
                    implied_prob_away=probs[2],
                )
                db.add(odds_snap)
                snap_cache[snap_key] = odds_snap

    await db.commit()
    await record_audit(
        db,
        admin_email=admin.email,
        action="IMPORT_CSV",
        target=req.league_id,
        details={
            "matches_inserted": inserted_matches,
            "matches_updated": updated_matches,
            "matches_skipped": skipped_matches,
            "aliases_created": aliases_created,
            "auto_train": req.auto_train,
        },
    )
    # record_audit flushes only; commit the audit row. The imported matches were
    # already committed above, so the audit describes a durable state.
    await db.commit()

    model_trained = False
    model_param_summary = None
    if req.auto_train and (inserted_matches > 0 or updated_matches > 0):
        try:
            from app.tasks.pipeline import train_league_task
            queued = train_league_task.delay(req.league_id, True)
            model_trained = False
            model_param_summary = {"status": "QUEUED", "task_id": queued.id}
        except Exception:
            model_param_summary = {"status": "QUEUE_UNAVAILABLE"}

    return {
        "status": "SUCCESS",
        "league_id": req.league_id,
        "matches_inserted": inserted_matches,
        "matches_updated": updated_matches,
        "matches_skipped": skipped_matches,
        "aliases_created": aliases_created,
        "model_trained": model_trained,
        "model_param": model_param_summary,
    }


@router.post("/sync-remote")
async def sync_remote_season(
    req: SyncRemoteRequest,
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Downloads historical CSV directly from football-data.co.uk for a given league code and season,
    then automatically commits the matches into the database.
    """
    if req.league_code not in LEAGUE_CODE_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported league code '{req.league_code}'. Supported: {list(LEAGUE_CODE_MAP.keys())}",
        )

    target_league_id, _target_country = LEAGUE_CODE_MAP[req.league_code]
    url = f"{FOOTBALL_DATA_BASE_URL}/{req.season}/{req.league_code}.csv"
    text_content = await _download_football_data_csv(req.season, req.league_code)

    commit_req = CommitCsvRequest(
        csv_content=text_content,
        league_id=target_league_id,
        season=req.season,
        alias_mappings={},
        auto_train=req.auto_train,
    )
    result = await commit_csv_import(commit_req, admin=admin, db=db)
    result["source_url"] = url
    return result
