"""偷菜 — 生成mouseTrail，每周期2次"""
import asyncio
import json
import logging
from app.services.qpet_client import QPetClient

logger = logging.getLogger(__name__)


class FarmSteal:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id

    @staticmethod
    def _gen_mouse_trail(length: int = 12) -> list:
        import random
        return [{"x": random.randint(10, 290), "y": random.randint(10, 290), "t": i * 33} for i in range(length)]

    async def run(self, friend_id: str, max_count: int = 2) -> int:
        """偷好友菜，返回成功次数"""
        status = await self._client.farm_get_friend(friend_id)
        if not status.get("success"):
            return 0

        slots = status.get("data", {}).get("slots", [])
        ripe = [s for s in slots if s.get("canSteal", s.get("state") == "ripe")]
        count = 0

        for slot in ripe[:max_count]:
            trail = self._gen_mouse_trail()
            ok = await self._client.farm_steal(friend_id, slot["slotIndex"], trail)
            if ok.get("success"):
                count += 1
                await asyncio.sleep(0.8)

        return count
