"""农场翻地 — 成熟作物翻地获得藏品残片"""
import asyncio
import logging
from app.services.qpet_client import QPetClient
from app.core.logger import info, warn

logger = logging.getLogger(__name__)


class FarmDig:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id

    async def run(self, slots: list[dict], is_premium: bool = False) -> int:
        """成熟作物翻地。VIP 用 explore-all，否则逐个 explore。
        返回翻地地块数。"""
        mature = [s for s in slots if s.get("state") == "mature"]
        if not mature:
            return 0

        if is_premium and len(mature) > 1:
            result = await self._client.farm_explore_all()
            if result.get("success"):
                count = result.get("data", {}).get("count", len(mature))
                info("农场", "翻地", f"一键翻地 {count}块", self._account_id)
                return count
            warn("农场", "翻地", "一键翻地API失败，回退单块翻", self._account_id)

        count = 0
        for slot in mature:
            ok = await self._client.farm_explore(slot["slotIndex"])
            if ok.get("success"):
                count += 1
                await asyncio.sleep(0.8)
        if count:
            info("农场", "翻地", f"翻地 {count}块", self._account_id)
        return count

    async def dig_friend(self, friend_id) -> int:
        """好友农场成熟作物翻地。返回翻地地块数。"""
        result = await self._client.farm_get_friend(friend_id)
        if not result.get("success"):
            return 0
        data = result.get("data", {})
        slots = data.get("slots", [])
        mature = [s for s in slots if s.get("state") == "mature"
                  and not s.get("alreadyExploredByVisitor", False)]
        if not mature:
            return 0

        count = 0
        for slot in mature:
            ok = await self._client.farm_explore_friend(friend_id, slot["slotIndex"])
            if ok.get("success"):
                count += 1
            await asyncio.sleep(2.0)
        return count
