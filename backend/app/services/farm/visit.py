"""农场访问 — 每日5EXP"""
import logging
from app.services.qpet_client import QPetClient

logger = logging.getLogger(__name__)


class FarmVisit:

    def __init__(self, client: QPetClient):
        self._client = client

    async def run(self) -> bool:
        result = await self._client.farm_claim_visit()
        ok = result.get("success", False)
        if not ok:
            logger.warning("农场访问API失败")
        return ok
