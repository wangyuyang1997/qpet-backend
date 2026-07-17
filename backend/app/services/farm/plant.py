"""农场播种 — 从 crop_cache 表读取PPM, 对齐旧引擎完整策略"""
import asyncio
import logging
from app.services.qpet_client import QPetClient
from sqlalchemy import text

logger = logging.getLogger(__name__)

VIP_CROPS = {
    "quinoa", "acai", "vanilla", "matsutake", "cordyceps",
    "black_truffle", "ghost_orchid", "kadupul", "rafflesia", "tian_shan_snow",
}


async def _get_crop_cache(engine_db) -> list[dict]:
    """从 crop_cache 表读取预计算作物数据"""
    result = await engine_db.execute(text("SELECT id, name, growth_minutes, rarity, level_required, exp_reward, seed_cost, profit, ppm, double_cost, double_profit, double_ppm, is_vip FROM crop_cache"))
    rows = result.fetchall()
    return [dict(r._mapping) for r in rows]


def _build_ranking_from_cache(cache_rows: list[dict], farm_level: int, is_vip: bool) -> list[dict]:
    """从缓存表构建PPM排名, 含双倍variant"""
    ranking = []
    for c in cache_rows:
        if c["level_required"] > farm_level:
            continue
        if not is_vip and c["id"] in VIP_CROPS:
            continue
        growth = c["growth_minutes"]

        # Normal variant
        entry = {
            "id": c["id"], "name": c["name"], "growth": growth,
            "exp": c["exp_reward"], "cost": c["seed_cost"],
            "profit": c["profit"], "ppm": float(c["ppm"]),
            "rarity": c["rarity"], "is_double": False,
        }
        ranking.append(entry)

        # Double variant (growth<=240, d_ppm >= normal_ppm)
        if growth <= 240 and c["double_ppm"] >= c["ppm"]:
            ranking.append({
                **entry,
                "exp": c["exp_reward"] * 2,
                "cost": c["double_cost"],
                "profit": c["double_profit"],
                "ppm": float(c["double_ppm"]),
                "is_double": True,
            })

    ranking.sort(key=lambda x: (-x["ppm"], x["growth"]))
    return ranking


class FarmPlant:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id
        self._planted = 0

    def _pick_missing(self, ranking: list[dict], collection: list[dict]) -> dict | None:
        """图鉴补缺: 选PPM最高的图鉴未齐作物(仅普通variant)
        图鉴品质(normal/fine/rare)与作物品质(normal/fine/rare/legend)互不关联。
        一个作物需要集齐图鉴三种品质才算完成。"""
        # 统计每个cropId已收集的图鉴品质
        crop_qualities: dict[str, set] = {}
        for c in collection:
            cid = c.get("cropId")
            q = c.get("quality", "")
            if cid and q in ("normal", "fine", "rare"):
                crop_qualities.setdefault(cid, set()).add(q)
        for r in ranking:
            if r["is_double"]:
                continue
            collected = crop_qualities.get(r["id"], set())
            if len(collected) < 3:
                return r
        return None

    def _pick_diversity(self, ranking: list[dict], farm_level: int, count: int,
                        planted_ids: set, best_id: str) -> list[dict]:
        """多样性: 最快count种(非VIP, 非best, 非已种), 只取普通variant"""
        normals = [r for r in ranking if not r["is_double"]
                   and r["id"] != best_id
                   and r["id"] not in planted_ids
                   and r["id"] not in VIP_CROPS]
        normals.sort(key=lambda r: r["growth"])
        return normals[:count]

    async def _plant_one(self, slot_index: int, crop: dict) -> bool:
        ok = await self._client.farm_plant(slot_index, crop["id"])
        if not ok.get("success"):
            return False
        if crop.get("is_double"):
            await asyncio.sleep(0.4)
            item_ok = await self._client.farm_use_item(slot_index, "double_exp")
            if not item_ok.get("success"):
                logger.warning(f"[{self._account_id}] 双倍道具使用失败 slot={slot_index}")
        return True

    async def run(self, slots: list[dict], crops: list[dict], collection: list[dict],
                  current_exp: int, is_premium: bool, vip_slot_index: int,
                  tasks: list[dict], farm_level: int, db) -> int:
        empty = [s for s in slots if s.get("canPlant") or (s.get("state") in ("empty", None) and not s.get("cropId"))]
        if not empty:
            return 0

        cache_rows = await _get_crop_cache(db)
        if not cache_rows:
            return 0

        ranking = _build_ranking_from_cache(cache_rows, farm_level, is_premium)
        if not ranking:
            return 0

        best = next((r for r in ranking if r["cost"] <= current_exp), ranking[-1])
        planted = 0

        # 1. VIP slot
        vip_slot = next((s for s in empty if s["slotIndex"] == vip_slot_index), None)
        if is_premium and vip_slot:
            if await self._plant_one(vip_slot["slotIndex"], best):
                planted += 1
                empty.remove(vip_slot)
                await asyncio.sleep(0.6)

        # 2. 图鉴补缺 (slot 0)
        used_completion = False
        if empty:
            missing = self._pick_missing(ranking, collection)
            if missing and empty[0].get("slotIndex") == 0:
                if await self._plant_one(empty[0]["slotIndex"], missing):
                    planted += 1
                    used_completion = True
                    empty.pop(0)
                    await asyncio.sleep(0.6)

        # 3. 多样性 (next 3 slots)
        variety_task = next((t for t in tasks if t.get("type") == "plant_variety"), None)
        div_idx = 0
        if empty and variety_task:
            need = variety_task.get("target", 3) - variety_task.get("current", 0)
            if need > 0:
                planted_ids = {s.get("cropId") for s in slots if s.get("cropId")}
                others = self._pick_diversity(ranking, farm_level, need, planted_ids, best["id"])
                for slot in empty[:need]:
                    pick = others[div_idx % len(others)] if others else best
                    if await self._plant_one(slot["slotIndex"], pick):
                        planted += 1
                        div_idx += 1
                        await asyncio.sleep(0.6)
                empty = [s for s in empty if not any(
                    s["slotIndex"] == e["slotIndex"] for e in empty[:need])]

        # 4. Rest
        for slot in empty:
            if await self._plant_one(slot["slotIndex"], best):
                planted += 1
                await asyncio.sleep(0.6)

        if planted:
            self._planted += planted
            from app.core.logger import action as log_action
            tag = "×2" if best.get("is_double") else ""
            log_action("农场", "播种", f"播种 {planted}块 → {best['name']}{tag} (成本{best['cost']} | 回报{best['exp']} | {best['growth']}分钟)", self._account_id)
        return planted
