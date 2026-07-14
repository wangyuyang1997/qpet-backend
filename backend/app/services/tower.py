"""爬塔自动化 — 免费优先，还魂丹可配置"""
import logging
from app.services.qpet_client import QPetClient
from app.services.config_service import ConfigService
from app.services.item_supply import ItemSupply

logger = logging.getLogger(__name__)


class Tower:
    """爬塔 service，每账号一个实例"""

    def __init__(self, client: QPetClient, config_svc: ConfigService, supply: ItemSupply, account_id: str):
        self._client = client
        self._config = config_svc
        self._supply = supply
        self._account_id = account_id

    async def run(self) -> dict:
        """一次完整的爬塔流程"""
        status = await self._client.get_tower_status()
        if not status.get("success"):
            return {"ok": False, "reason": "获取塔状态失败"}

        data = status.get("data", {})
        max_floor = data.get("maxFloor", 0)
        remaining_free = data.get("remainingFreeCount", 0)
        revive_count = data.get("reviveCount", 0)

        if max_floor <= 0:
            return {"ok": False, "reason": "无可用楼层"}

        results = {"free_used": 0, "revive_used": 0}

        # —— 免费通道 ——
        while remaining_free > 0:
            ok = await self._do_floor(max_floor, use_revive=False)
            if not ok:
                break
            results["free_used"] += 1
            remaining_free -= 1

        # —— 还魂丹通道 ——
        use_revive = await self._config.get_bool(self._account_id, "tower_use_revive")
        if remaining_free <= 0 and use_revive:
            while True:
                # 补给
                await self._supply.ensure("revive", revive_count)
                status = await self._client.get_tower_status()
                data = status.get("data", {})
                revive_count = data.get("reviveCount", 0)
                if revive_count <= 0:
                    break

                ok = await self._do_floor(max_floor, use_revive=True)
                if not ok:
                    break
                results["revive_used"] += 1
                revive_count -= 1

        logger.info(f"[{self._account_id}] 爬塔完成: 免费{results['free_used']}次 还魂{results['revive_used']}次")
        return {"ok": True, **results}

    async def _do_floor(self, floor: int, use_revive: bool) -> bool:
        result = await self._client.prepare_tower(floor, use_revive)
        if not result.get("success"):
            return False
        battle_token = result.get("data", {}).get("battleToken", "")
        if not battle_token:
            return False
        settle = await self._client.settle_tower(battle_token, True)
        return settle.get("success", False)
