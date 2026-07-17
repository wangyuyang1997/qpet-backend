"""魂珠合成 — VIP一键合成，降级为手动merge"""
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
        """返回 {auto_merged, manual_merged}"""
        results = {"auto_merged": False, "manual_merged": False}

        beads = await self._client.get_bead_inventory()
        if not beads.get("success"):
            warn("乐斗", "魂珠", "获取魂珠背包API失败", self._account_id)
            return results

        data = beads.get("data", {})

        if is_premium:
            result = await self._client.auto_merge_beads("all", 8)
            if result.get("success"):
                results["auto_merged"] = True
                info("乐斗", "魂珠", "魂珠一键合成成功", self._account_id)
                return results
            warn("乐斗", "魂珠", "魂珠一键合成失败，回退手动", self._account_id)

        # 手动逐级合成
        for level in range(1, 8):
            result = await self._client.merge_beads("all", level + 1)
            if result.get("success"):
                results["manual_merged"] = True

        if results["manual_merged"]:
            info("乐斗", "魂珠", "魂珠手动合成成功", self._account_id)

        return results
