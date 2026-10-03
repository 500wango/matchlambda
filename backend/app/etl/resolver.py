import difflib
from typing import Optional, List, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Team, TeamAlias


class TeamResolver:
    """
    Team identity resolver adhering to docs/06_DATA_PIPELINE_ETL.md.
    - Resolves (source_name, external_id) first.
    - If external_id is absent, resolves confirmed (source_name, country, external_name) where external_id IS NULL.
    - Proposes fuzzy candidates restricted by country; NEVER auto-creates clubs/aliases or commits caller's transaction.
    - Returns canonical team_id or None (unresolved).
    """

    @staticmethod
    async def resolve_team(
        session: AsyncSession,
        source_name: str,
        external_name: str,
        country: str = "England",
        external_id: Optional[str] = None,
    ) -> Optional[str]:
        # 1. Resolve by stable external_id if present
        if external_id:
            stmt = select(TeamAlias.team_id).where(
                TeamAlias.source_name == source_name,
                TeamAlias.external_id == external_id,
            )
            result = await session.execute(stmt)
            team_id = result.scalar_one_or_none()
            if team_id:
                return team_id

        # 2. Resolve by confirmed name-only alias (where external_id IS NULL)
        stmt = select(TeamAlias.team_id).where(
            TeamAlias.source_name == source_name,
            TeamAlias.country == country,
            TeamAlias.external_name == external_name,
            TeamAlias.external_id.is_(None),
        )
        result = await session.execute(stmt)
        team_id = result.scalar_one_or_none()
        if team_id:
            return team_id

        # 3. Direct canonical name match
        stmt = select(Team.id).where(
            Team.canonical_name == external_name,
            Team.country == country,
        )
        result = await session.execute(stmt)
        team_id = result.scalar_one_or_none()
        if team_id:
            return team_id

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

        scored_candidates.sort(key=lambda x: x[2], reverse=True)
        return scored_candidates[:limit]

    @staticmethod
    async def log_unresolved_entity(
        session: AsyncSession,
        source_name: str,
        external_name: str,
        country: str = "England",
        external_id: Optional[str] = None,
        filepath: str = "data/rejected_entities.jsonl",
    ):
        """
        Appends ambiguous/unmatched entity to operator review file adhering to ETL spec.
        """
        import os
        import json
        from datetime import datetime, timezone

        candidates = await TeamResolver.propose_candidates(
            session=session,
            external_name=external_name,
            country=country,
        )

        os.makedirs(os.path.dirname(filepath), exist_ok=True)
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
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
