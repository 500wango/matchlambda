import difflib
from typing import Optional, List, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Team, TeamAlias


_INTERNATIONAL = {"europe", "world", "international", "uefa", "global"}

# Size cap for the operator review log. Once exceeded the file is rotated once
# to ``<name>.1`` so an un-attended resolver can never fill the disk.
_REJECTED_LOG_MAX_BYTES = 5 * 1024 * 1024


def _is_international(country: Optional[str]) -> bool:
    return (country or "").strip().lower() in _INTERNATIONAL


class TeamResolver:
    """
    Team identity resolver adhering to docs/06_DATA_PIPELINE_ETL.md.
    - Resolves (source_name, external_id) first.
    - If external_id is absent, resolves confirmed (source_name, country, external_name) where external_id IS NULL.
    - Falls back to a cross-country match for international competitions (UCL/UEL),
      disambiguating multiple candidates with a stable, documented priority so the
      same input always maps to the same team (never None when a candidate exists).
    - Proposes fuzzy candidates restricted by country; NEVER auto-creates clubs/aliases or commits caller's transaction.
    - Returns canonical team_id or None (unresolved).
    """

    @staticmethod
    async def _disambiguate(
        session: AsyncSession,
        source_name: str,
        candidates: List[Tuple[str, str]],
    ) -> Optional[str]:
        """Pick one team_id from ``(team_id, country)`` candidates deterministically.

        Priority (stable — same input, same result):
          1. a candidate that also carries a non-null ``external_id`` for this
             ``source_name`` (the "canonically registered" team),
          2. a candidate whose country is a real nation rather than an
             international bucket (``europe``/``world``/...),
          3. lexicographically smallest ``team_id``.
        """
        by_id: dict[str, str] = {}
        for team_id, country in candidates:
            if team_id in by_id:
                if _is_international(by_id[team_id]) and not _is_international(country):
                    by_id[team_id] = country
            else:
                by_id[team_id] = country
        if not by_id:
            return None
        if len(by_id) == 1:
            return next(iter(by_id))

        ids = list(by_id)
        stmt = select(TeamAlias.team_id).where(
            TeamAlias.source_name == source_name,
            TeamAlias.team_id.in_(ids),
            TeamAlias.external_id.isnot(None),
        )
        has_stable_external = set((await session.execute(stmt)).scalars().all())
        return sorted(
            ids,
            key=lambda tid: (tid not in has_stable_external, _is_international(by_id[tid]), tid),
        )[0]

    @staticmethod
    async def resolve_team(
        session: AsyncSession,
        source_name: str,
        external_name: str,
        country: str = "England",
        external_id: Optional[str] = None,
    ) -> Optional[str]:
        # 1. Resolve by stable external_id if present (unique per source).
        if external_id:
            stmt = (
                select(TeamAlias.team_id)
                .where(
                    TeamAlias.source_name == source_name,
                    TeamAlias.external_id == external_id,
                )
                .order_by(TeamAlias.team_id.asc())
            )
            result = await session.execute(stmt)
            team_id = result.scalars().first()
            if team_id:
                return team_id

        relaxed = _is_international(country)

        # 2. Exact-country match on a confirmed name-only alias.
        stmt = select(TeamAlias.team_id, TeamAlias.country).where(
            TeamAlias.source_name == source_name,
            TeamAlias.external_name == external_name,
            TeamAlias.external_id.is_(None),
            TeamAlias.country == country,
        )
        exact_rows = list((await session.execute(stmt)).all())
        if exact_rows:
            # The unique partial index uq_alias_confirmed_name keeps this to one
            # row per (source, country, name); the helper is defensive only.
            return await TeamResolver._disambiguate(session, source_name, exact_rows)

        # 3. For international competitions only, relax the country filter and
        #    disambiguate deterministically instead of dropping the event.
        if relaxed:
            stmt = select(TeamAlias.team_id, TeamAlias.country).where(
                TeamAlias.source_name == source_name,
                TeamAlias.external_name == external_name,
                TeamAlias.external_id.is_(None),
            )
            relaxed_rows = list((await session.execute(stmt)).all())
            if relaxed_rows:
                return await TeamResolver._disambiguate(session, source_name, relaxed_rows)

        # 4. Direct canonical name match. Cups do not share one country with every club.
        stmt = select(Team.id, Team.country).where(Team.canonical_name == external_name)
        if not relaxed:
            stmt = stmt.where(Team.country == country)
        name_rows = list((await session.execute(stmt)).all())
        if name_rows:
            return await TeamResolver._disambiguate(session, source_name, name_rows)

        return None

    @staticmethod
    async def propose_candidates(
        session: AsyncSession,
        external_name: str,
        country: str = "England",
        cutoff: float = 0.6,
        limit: int = 3,
    ) -> List[Tuple[str, str, float]]:
        """
        Propose candidates for operator review.
        Returns list of (team_id, canonical_name, similarity_score).
        Never commits or auto-inserts.
        """
        stmt = select(Team.id, Team.canonical_name).where(Team.country == country)
        result = await session.execute(stmt)
        teams = result.all()

        scored_candidates = []
        for team_id, name in teams:
            ratio = difflib.SequenceMatcher(None, external_name.lower(), name.lower()).ratio()
            if ratio >= cutoff:
                scored_candidates.append((team_id, name, round(ratio, 4)))

        scored_candidates.sort(key=lambda x: (x[2], x[0]), reverse=True)
        return scored_candidates[:limit]

    @staticmethod
    async def log_unresolved_entity(
        session: AsyncSession,
        source_name: str,
        external_name: str,
        country: str = "England",
        external_id: Optional[str] = None,
        filepath: Optional[str] = None,
    ):
        """
        Appends ambiguous/unmatched entity to operator review file adhering to ETL spec.
        Never raises: best-effort logging so a full/read-only disk cannot break ingestion.
        Rotates the file once it grows past _REJECTED_LOG_MAX_BYTES so it cannot grow
        without bound.
        """
        import json
        import asyncio
        import logging
        from pathlib import Path
        from datetime import datetime, timezone

        logger = logging.getLogger(__name__)

        candidates = await TeamResolver.propose_candidates(
            session=session,
            external_name=external_name,
            country=country,
        )

        if filepath is None:
            # backend/data/rejected_entities.jsonl (absolute, CWD-independent)
            filepath = str(Path(__file__).resolve().parent.parent.parent / "data" / "rejected_entities.jsonl")

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source_name": source_name,
            "external_id": external_id,
            "external_name": external_name,
            "country": country,
            "suggested_candidates": [
                {"team_id": cid, "canonical_name": cname, "score": score}
                for cid, cname, score in candidates
            ],
        }

        def _write() -> None:
            import os
            path = Path(filepath)
            path.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(entry, ensure_ascii=False) + "\n"
            try:
                if path.exists() and path.stat().st_size > _REJECTED_LOG_MAX_BYTES:
                    # Rotate once, keeping a single bounded backup.
                    os.replace(path, str(path) + ".1")
            except OSError:
                pass
            with open(path, "a", encoding="utf-8") as handle:
                try:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                except (ImportError, OSError):
                    pass
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())

        try:
            await asyncio.to_thread(_write)
        except OSError as exc:
            logger.warning("Could not log unresolved entity: %s", exc)
