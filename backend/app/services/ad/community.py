"""社区广告 — 5次/天，30分冷却"""
import logging
from app.services.qpet_client import QPetClient

logger = logging.getLogger(__name__)


class AdCommunity:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id

    async def run(self) -> bool:
        status = await self._client.community_get_ad_status()
        if not status.get("success"):
            return False
        if not status.get("data", {}).get("available", False):
            return False
        result = await self._client.community_claim_ad()
        if result.get("success"):
            logger.info(f"[{self._account_id}] 社区广告领取成功")
            return True
        return False
