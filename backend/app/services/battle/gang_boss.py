"""帮派BOSS — 免费挑战优先，挑战书可配置补充"""
import logging
from app.services.qpet_client import QPetClient
from app.services.config_service import ConfigService
from app.services.item_supply import ItemSupply

logger = logging.getLogger(__name__)


class GangBoss:
    """帮派BOSS service，每账号一个实例"""

    def __init__(self, client: QPetClient, config_svc: ConfigService, supply: ItemSupply, account_id: str):
        self._client = client
        self._config = config_svc
        self._supply = supply
        self._account_id = account_id

    async def run(self) -> dict:
        status = await self._client.get_gang_boss_status()
        if not status.get("success"):
            return {"ok": False, "reason": "获取帮派BOSS状态失败"}

        data = status.get("data", {})
        bosses = data.get("bosses", [])

        used = 0

        for boss in bosses:
            boss_id = boss.get("bossId") or boss.get("id", "")
            free_remaining = boss.get("freeChallengeRemaining", 0)

            # 免费挑战
            while free_remaining > 0:
                ok = await self._do_boss(boss_id)
                if not ok:
                    break
                used += 1
                free_remaining -= 1

            # 挑战书补充
            if free_remaining <= 0:
                await self._supply.ensure("challenge_book", 0)
                ok = await self._do_boss(boss_id)
                if ok:
                    used += 1

        logger.info(f"[{self._account_id}] 帮派BOSS完成: {used}次")
        return {"ok": True, "used": used}

    async def _do_boss(self, boss_id: str) -> bool:
        result = await self._client.prepare_gang_boss(boss_id)
        if not result.get("success"):
            return False
        battle_token = result.get("data", {}).get("battleToken", "")
        if not battle_token:
            return False
        settle = await self._client.settle_gang_boss(battle_token, True)
        return settle.get("success", False)
