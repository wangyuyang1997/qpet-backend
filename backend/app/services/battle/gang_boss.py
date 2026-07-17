"""帮派BOSS — 免费挑战优先，挑战书补充"""
import logging
from app.services.qpet_client import QPetClient
from app.services.config_service import ConfigService
from app.services.item_supply import ItemSupply
from app.core.logger import action as log_action, info, warn

logger = logging.getLogger(__name__)


class GangBoss:

    def __init__(self, client: QPetClient, config_svc: ConfigService, supply: ItemSupply, account_id: str):
        self._client = client
        self._config = config_svc
        self._supply = supply
        self._account_id = account_id
        self.today_count = 0
        self.today_contrib = 0

    async def run(self) -> dict:
        status = await self._client.get_gang_boss_status()
        if not status.get("success"):
            warn("乐斗", "帮派BOSS", "获取帮派BOSS状态API失败", self._account_id)
            return {"ok": False, "reason": "获取帮派BOSS状态失败"}

        data = status.get("data", {})
        bosses = data.get("bossList", [])

        # 从API同步今日贡献（重启不丢，不用本地计数）
        total_contrib = 0
        for boss in bosses:
            total_contrib += boss.get("todayContribEarned", 0) or 0
        self.today_contrib = total_contrib

        used = 0

        # 筛选可挑战的已解锁BOSS（通常按等级升序）
        unlocked = [b for b in bosses if b.get("unlocked") and b.get("canChallenge")]
        if not unlocked:
            return {"ok": True, "used": 0}

        # 免费挑战：所有解锁BOSS各打一次
        for boss in unlocked:
            if not boss.get("freeChallengeDone", True):
                ok = await self._do_boss(boss.get("id"))
                if ok:
                    used += 1

        # 挑战书：用在最高等级BOSS上，一次循环用多本（每日上限15次）
        top_boss = unlocked[-1]
        daily_limit = data.get("dailyLimit", 15)
        remaining = daily_limit - (data.get("todayCount", 0) or 0) - used
        while remaining > 0 and await self._supply.ensure("challenge_book", 0):
            ok = await self._do_boss(top_boss.get("id"))
            if ok:
                used += 1
                remaining -= 1
            else:
                break  # prepare/settle失败，不再继续

        if used:
            info("乐斗", "帮派BOSS", f"帮派BOSS完成: {used}次, 最高BOSS={top_boss.get('name', top_boss.get('id'))}", self._account_id)
        return {"ok": True, "used": used}

    async def _do_boss(self, boss_id: int) -> bool:
        result = await self._client.prepare_gang_boss(boss_id)
        if not result.get("success"):
            warn("乐斗", "帮派BOSS", f"准备BOSS#{boss_id}失败", self._account_id)
            return False
        battle_token = result.get("data", {}).get("battleToken", "")
        if not battle_token:
            warn("乐斗", "帮派BOSS", f"BOSS#{boss_id}缺少battleToken", self._account_id)
            return False
        settle = await self._client.settle_gang_boss(battle_token, True)
        if settle.get("success"):
            self.today_count += 1
            contrib = (settle.get("data", {}) or {}).get("rewards", {}).get("contribution", 0)
            self.today_contrib += contrib
            log_action("乐斗", "帮派BOSS", f"BOSS#{boss_id}: {'胜' if contrib > 0 else '败'} +{contrib}贡献", self._account_id)
            return True
        warn("乐斗", "帮派BOSS", f"BOSS#{boss_id}结算失败", self._account_id)
        return False
