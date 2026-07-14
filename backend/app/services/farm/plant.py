"""农场播种 — 最优作物算法 + 图鉴补缺 + 多样性"""
import asyncio
import logging
from app.services.qpet_client import QPetClient

logger = logging.getLogger(__name__)


class FarmPlant:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id

    def _best_crop(self, crops: list[dict], current_exp: int) -> dict | None:
        """按利润/分钟(PPM)排序，返回EXP够买的最高PPM作物"""
        candidates = []
        for c in crops:
            price = c.get("price", 0)
            if current_exp < price:
                continue
            growth = c.get("growthTime", 1)
            profit = c.get("sellPrice", 0) - price
            ppm = profit / (growth / 60) if growth > 0 else 0
            candidates.append((ppm, c))

        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    def _missing_crop(self, collection: list[dict], crops: list[dict], current_exp: int) -> dict | None:
        """图鉴补缺：未收集的最高品质+最短生长的作物"""
        collected = {c.get("cropId") for c in collection if c.get("collected")}
        missing = [c for c in crops if c.get("id") not in collected and current_exp >= c.get("price", 0)]
        if not missing:
            return None
        missing.sort(key=lambda c: (-c.get("quality", 0), c.get("growthTime", 9999)))
        return missing[0]

    async def run(self, slots: list[dict], crops: list[dict], collection: list[dict],
                  current_exp: int, is_premium: bool, vip_slot_index: int,
                  tasks: list[dict]) -> int:
        """返回播种地块数。优先级: VIP黑土 → 图鉴补缺 → 多样性 → 其余最优"""
        empty = [s for s in slots if s.get("state") in ("empty", None) and not s.get("cropId")]
        if not empty:
            return 0

        best = self._best_crop(crops, current_exp)
        if not best:
            return 0

        planted = 0

        # 1. VIP黑土
        vip_slot = next((s for s in empty if s["slotIndex"] == vip_slot_index), None)
        if is_premium and vip_slot:
            ok = await self._client.farm_plant(vip_slot["slotIndex"], best["id"])
            if ok.get("success"):
                planted += 1
                empty.remove(vip_slot)
                await asyncio.sleep(0.6)

        # 2. 图鉴补缺
        if empty:
            missing = self._missing_crop(collection, crops, current_exp)
            if missing:
                slot = empty[0]
                ok = await self._client.farm_plant(slot["slotIndex"], missing["id"])
                if ok.get("success"):
                    planted += 1
                    empty.pop(0)
                    await asyncio.sleep(0.6)

        # 3. 多样性
        variety_task = next((t for t in tasks if "variety" in t.get("name", "").lower()), None)
        if empty and variety_task and variety_task.get("current", 0) < variety_task.get("target", 3):
            fastest = sorted(crops, key=lambda c: c.get("growthTime", 9999))[:3]
            for i, slot in enumerate(empty[:3]):
                crop = fastest[i % len(fastest)]
                ok = await self._client.farm_plant(slot["slotIndex"], crop["id"])
                if ok.get("success"):
                    planted += 1
                    await asyncio.sleep(0.6)
            empty = [s for s in empty if not any(
                s["slotIndex"] == e["slotIndex"] for e in empty[:3]
            )]

        # 4. 其余最优
        for slot in empty:
            ok = await self._client.farm_plant(slot["slotIndex"], best["id"])
            if ok.get("success"):
                planted += 1
                await asyncio.sleep(0.6)

        return planted
