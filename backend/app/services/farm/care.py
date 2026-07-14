"""农场照料 — 自己浇水+帮好友"""
import asyncio
import logging
from app.services.qpet_client import QPetClient

logger = logging.getLogger(__name__)


class FarmCare:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id

    async def water_own(self, slots: list[dict]) -> int:
        """自己浇水，每日5次上限"""
        need_water = [s for s in slots if s.get("needsWater", False)]
        count = 0
        for slot in need_water[:5]:
            ok = await self._client.farm_care(slot["slotIndex"])
            if ok.get("success"):
                count += 1
                await asyncio.sleep(0.5)
        return count

    async def water_friend(self, friend_id: str, max_count: int = 3) -> int:
        """帮好友浇水"""
        status = await self._client.farm_get_friend(friend_id)
        if not status.get("success"):
            return 0

        slots = status.get("data", {}).get("slots", [])
        need_water = [s for s in slots if s.get("needsWater", False)]

        count = 0
        for slot in need_water[:max_count]:
            ok = await self._client.farm_help_friend(friend_id, slot["slotIndex"])
            if ok.get("success"):
                count += 1
                await asyncio.sleep(0.6)
        return count
