"""广告体力 — 30分冷却，体力>80跳过"""
import logging
from app.services.qpet_client import QPetClient

logger = logging.getLogger(__name__)


class AdStamina:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id

    async def run(self, current_stamina: int = 0) -> bool:
        if current_stamina > 80:
            return False
        status = await self._client.get_ad_stamina_status()
        if not status.get("success"):
            return False
        if not status.get("data", {}).get("available", False):
            return False
        result = await self._client.claim_ad_stamina()
        if result.get("success"):
            logger.info(f"[{self._account_id}] 广告体力领取成功")
            return True
        return False
