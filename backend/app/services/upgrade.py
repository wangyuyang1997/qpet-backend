"""魂珠合成 — 逐类型读 mergeRules，够数量就合，对齐旧 engine.js:1535-1563"""
import asyncio
import logging
from app.services.qpet_client import QPetClient
from app.services.item_supply import ItemSupply
from app.core.logger import info, warn

logger = logging.getLogger(__name__)


class Upgrade:

    def __init__(self, client: QPetClient, supply: ItemSupply, account_id: str):
        self._client = client
        self._supply = supply
        self._account_id = account_id

    async def run(self, is_premium: bool = False) -> dict:
        beads = await self._client.get_bead_inventory()
        if not beads.get("success"):
            warn("乐斗", "魂珠", "获取魂珠背包API失败", self._account_id)
            return {"merged": 0}

        data = beads.get("data", {})
        inv = data.get("inventory", {})
        if not inv:
            return {"merged": 0}

        types = data.get("beadTypes") or list(inv.keys())
        rules = data.get("mergeRules", {})
        if not rules:
            warn("乐斗", "魂珠", "魂珠API无mergeRules，跳过合成", self._account_id)
            return {"merged": 0}

        merged = 0
        for bead_type in types:
            counts = inv.get(bead_type, {})
            for tgt_str in sorted(rules.keys(), key=lambda x: int(x)):
                tgt = int(tgt_str)
                rule = rules[tgt_str]
                from_lv = rule.get("from", 0)
                needed = rule.get("needed", 3)

                if (counts.get(from_lv, 0) or 0) >= needed:
                    r = await self._client.auto_merge_beads(bead_type, tgt)
                    if not r.get("success"):
                        r = await self._client.merge_beads(bead_type, tgt)
                    if r.get("success"):
                        merged += 1
                        info("乐斗", "魂珠", f"合成: {bead_type} Lv{from_lv}→{tgt}", self._account_id)
                        await asyncio.sleep(0.3)

        if merged:
            info("乐斗", "魂珠", f"魂珠合成完成: {merged}次", self._account_id)
        return {"merged": merged}
