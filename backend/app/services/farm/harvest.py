"""农场收获 — 单块/一键/铲除枯萎"""
import asyncio
import logging
from app.services.qpet_client import QPetClient
from app.core.logger import action as log_action

logger = logging.getLogger(__name__)


class FarmHarvest:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id
        self._harvested = 0

    async def run(self, slots: list[dict], is_premium: bool = False) -> int:
        harvestable = [s for s in slots if s.get("canHarvest", False)]
        if not harvestable:
            return 0

        total_exp = 0
        if is_premium and len(harvestable) == len(slots):
            result = await self._client.farm_harvest_all()
            if result.get("success"):
                for s in harvestable:
                    total_exp += s.get("expReward", 0)
                log_action("农场", "收获", f"一键收获 {len(harvestable)}块 +{total_exp}EXP", self._account_id)
                self._harvested += len(harvestable)
                return len(harvestable)

        count = 0
        for slot in harvestable:
            ok = await self._client.farm_harvest(slot["slotIndex"])
            if ok.get("success"):
                count += 1
                total_exp += slot.get("expReward", 0)
                log_action("农场", "收获", f"地块{slot['slotIndex']+1} → {slot.get('cropName','?')}: +{slot.get('expReward','?')}EXP", self._account_id)
                await asyncio.sleep(0.8)
        self._harvested += count
        return count

    async def remove_withered(self, slots: list[dict]) -> int:
        withered = [s for s in slots if s.get("state") == "withered"]
        count = 0
        for slot in withered:
            ok = await self._client.farm_remove(slot["slotIndex"])
            if ok.get("success"):
                count += 1
                log_action("农场", "铲除", f"地块{slot['slotIndex']+1} 枯萎已铲除 ({slot.get('cropName','')})", self._account_id)
                await asyncio.sleep(0.6)
        return count
