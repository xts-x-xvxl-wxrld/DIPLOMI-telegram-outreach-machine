from __future__ import annotations

from backend.db.models import Community, SeedChannel
from backend.services.seed_expansion import DiscoveredCommunityCandidate, SeedExpansionAdapter
from backend.workers.account_manager import AccountLease


class TelethonSeedExpansionAdapter(SeedExpansionAdapter):
    """Minimal adapter shell; real graph inspection can fill this in without changing tests."""

    def __init__(self, lease: AccountLease) -> None:
        self.lease = lease

    async def discover_from_seed(
        self,
        *,
        seed_channel: SeedChannel,
        source_community: Community,
        depth: int,
    ) -> list[DiscoveredCommunityCandidate]:
        return []

    async def aclose(self) -> None:
        return None
