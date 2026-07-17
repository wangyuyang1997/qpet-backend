"""爬塔自动化 — 免费优先，还魂丹可配置"""
import logging
from app.services.qpet_client import QPetClient
from app.services.config_service import ConfigService
from app.services.item_supply import ItemSupply
from app.core.logger import action as log_action, warn, info

logger = logging.getLogger(__name__)


class Tower:

    def __init__(self, client: QPetClient, config_svc: ConfigService, supply: ItemSupply, account_id: str):
        self._client = client
        self._config = config_svc
        self._supply = supply
        self._account_id = account_id

    async def run(self) -> dict:
        status = await self._client.get_tower_status()
        if not status.get("success"):
            warn("乐斗", "爬塔", "获取爬塔状态API失败", self._account_id)
            return {"ok": False, "reason": "获取塔状态失败"}

        data = status.get("data", {})
        max_floor = data.get("maxFloor", 0)
        remaining_free = data.get("remainingFreeCount", 0)
        revive_count = data.get("reviveCount", 0)

        if max_floor <= 0:
            return {"ok": False, "reason": "无可用楼层"}

        results = {"free_used": 0, "revive_used": 0, "total_exp": 0}

        # —— 免费通道 ——
        while remaining_free > 0:
            ok, exp = await self._do_floor(max_floor, use_revive=False)
            if not ok:
                break
            results["free_used"] += 1
            results["total_exp"] += exp
            log_action("乐斗", "爬塔", f"第{max_floor}层: {'胜' if exp > 0 else '败'} +{exp}EXP", self._account_id)
            remaining_free -= 1

        # —— 还魂丹通道 ——
        use_revive = await self._config.get_bool(self._account_id, "tower_use_revive")
        if remaining_free <= 0 and use_revive:
            while True:
                await self._supply.ensure("revive", revive_count)
                status = await self._client.get_tower_status()
                data = status.get("data", {})
                revive_count = data.get("reviveCount", 0)
                if revive_count <= 0:
                    break

                ok, exp = await self._do_floor(max_floor, use_revive=True)
                if not ok:
                    break
                results["revive_used"] += 1
                results["total_exp"] += exp
                log_action("乐斗", "爬塔", f"第{max_floor}层(还魂): {'胜' if exp > 0 else '败'} +{exp}EXP", self._account_id)
                revive_count -= 1

        if results["free_used"] or results["revive_used"]:
            info("乐斗", "爬塔", f"爬塔完成: 免费{results['free_used']}次 还魂{results['revive_used']}次 +{results['total_exp']}EXP", self._account_id)

        return {"ok": True, **results}

    async def _do_floor(self, floor: int, use_revive: bool) -> tuple[bool, int]:
        result = await self._client.prepare_tower(floor, use_revive)
        if not result.get("success"):
            warn("乐斗", "爬塔", f"准备第{floor}层失败", self._account_id)
            return False, 0
        battle_token = result.get("data", {}).get("battleToken", "")
        if not battle_token:
            warn("乐斗", "爬塔", f"第{floor}层缺少battleToken", self._account_id)
            return False, 0
        settle = await self._client.settle_tower(battle_token, True)
        if settle.get("success"):
            exp = settle.get("data", {}).get("exp", 0) or settle.get("data", {}).get("expGained", 0) or 0
            return True, exp
        warn("乐斗", "爬塔", f"第{floor}层结算失败", self._account_id)
        return False, 0
