"""农场广告 — 5次/天，30分冷却。对齐旧引擎 autoFarm()#4"""
import logging
from app.services.qpet_client import QPetClient

logger = logging.getLogger(__name__)


class AdFarm:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id
        self.today_count = 0

    async def run(self) -> bool:
        status = await self._client.farm_get_ad_status()
        if not status.get("success"):
            return False
        data = status.get("data", {})
        # 每次都从API同步真实计数（重启不丢）
        self.today_count = data.get("todayCount", 0) or 0
        if not data.get("canClaim", False):
            return False
        result = await self._client.farm_claim_ad()
        if result.get("success"):
            self.today_count = (data.get("todayCount", 0) or 0) + 1
            from app.core.logger import action as log_action
            log_action("农场", "农场", f"广告奖励 +{data.get('expPerClaim', '?')}EXP ({self.today_count}/{data.get('maxDaily', 5)})", self._account_id)
            return True
        return False
