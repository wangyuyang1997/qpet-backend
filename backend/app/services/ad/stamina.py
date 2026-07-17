"""广告体力 — 30分冷却，体力>80跳过。对齐旧引擎 autoAdStamina()"""
import logging
from app.services.qpet_client import QPetClient
from app.core.logger import info, warn

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
            warn("乐斗", "广告", "获取广告体力状态API失败", self._account_id)
            return False
        data = status.get("data", {})
        # 每次都从API同步真实计数（重启不丢）
        self.today_count = data.get("todayCount", 0) or 0
        if not data.get("canClaim", False):
            return False
        result = await self._client.claim_ad_stamina()
        if result.get("success"):
            self.today_count = (data.get("todayCount", 0) or 0) + 1
            info("乐斗", "广告", f"广告体力领取成功 ({self.today_count}/{data.get('maxDaily', 10)})", self._account_id)
            return True
        warn("乐斗", "广告", "广告体力领取失败", self._account_id)
        return False
