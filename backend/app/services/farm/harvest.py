"""农场收获 — 单块/一键/铲除枯萎"""
import asyncio
import logging
from app.services.qpet_client import QPetClient

logger = logging.getLogger(__name__)


class FarmHarvest:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id

    async def run(self, slots: list[dict], is_premium: bool = False) -> int:
        """返回收获地块数"""
        harvestable = [s for s in slots if s.get("canHarvest", False)]
        if not harvestable:
            return 0

        if is_premium and len(harvestable) == len(slots):
            result = await self._client.farm_harvest_all()
            if result.get("success"):
                logger.info(f"[{self._account_id}] 一键收获 {len(harvestable)}块")
                return len(harvestable)

        count = 0
        for slot in harvestable:
            ok = await self._client.farm_harvest(slot["slotIndex"])
            if ok.get("success"):
                count += 1
                await asyncio.sleep(0.8)
        return count

    async def remove_withered(self, slots: list[dict]) -> int:
        """铲除枯萎作物"""
        withered = [s for s in slots if s.get("state") == "withered"]
        count = 0
        for slot in withered:
            ok = await self._client.farm_remove(slot["slotIndex"])
            if ok.get("success"):
                count += 1
                await asyncio.sleep(0.6)
        return count
