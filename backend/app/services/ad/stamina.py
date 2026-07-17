"""广告体力 — 30分冷却，体力>80跳过。对齐旧引擎 autoAdStamina()"""
import logging
from app.services.qpet_client import QPetClient

logger = logging.getLogger(__name__)


class AdStamina:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id
        self.today_count = 0

    async def run(self, current_stamina: int = 0) -> bool:
        if current_stamina > 80:
            return False
        status = await self._client.get_ad_stamina_status()
        if not status.get("success"):
            return False
        data = status.get("data", {})
        # 每次都从API同步真实计数（重启不丢）
        self.today_count = data.get("todayCount", 0) or 0
        if not data.get("canClaim", False):
            return False
        result = await self._client.claim_ad_stamina()
        if result.get("success"):
            self.today_count = (data.get("todayCount", 0) or 0) + 1
            logger.info(f"[{self._account_id}] 广告体力领取成功 ({self.today_count}/{data.get('maxDaily', 10)})")
            return True
        return False
