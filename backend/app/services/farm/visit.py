"""农场访问 — 每日5EXP"""
from app.services.qpet_client import QPetClient


class FarmVisit:

    def __init__(self, client: QPetClient):
        self._client = client

    async def run(self) -> bool:
        result = await self._client.farm_claim_visit()
        return result.get("success", False)
