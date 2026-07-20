"""宝箱自动化 — 展览厅宝箱，对齐旧引擎 autoChest()
支持配置项 chest_budget: free=仅免费, 100/200/300=开到对应档位"""
import logging
from app.services.qpet_client import QPetClient
from app.core.logger import action as log_action, warn

logger = logging.getLogger(__name__)

BUDGET_LIMITS = {"free": 0, "100": 100, "200": 200, "300": 300}


class Chest:

    def __init__(self, client: QPetClient, account_id: str, config=None):
        self._client = client
        self._account_id = account_id
        self._config = config

    async def run(self) -> bool:
        budget_key = "free"
        if self._config:
            budget_key = await self._config.get_value(self._account_id, "chest_budget") or "free"
        max_cost = BUDGET_LIMITS.get(budget_key, 0)

        status = await self._client.get_chest_status()
        if not status.get("success"):
            warn("乐斗", "日常", "获取宝箱状态失败", self._account_id)
            return False
        data = status.get("data", {})
        next_cost = data.get("nextCost", 0) or 0
        today_count = data.get("todayCount", 0) or 0

        # 以服务端状态为准：nextCost > 预算上限 才跳过
        if next_cost > max_cost:
            return True

        opened = 0
        while next_cost <= max_cost:
            result = await self._client.open_chest()
            if result.get("success"):
                opened += 1
                drops = result.get("data", {}).get("drops", [])
                items = ", ".join(f"{d.get('item_name','?')}×{d.get('quantity',1)}" for d in drops)
                cost_label = "免费" if next_cost == 0 else f"{next_cost}EXP"
                log_action("乐斗", "日常", f"宝箱 #{opened} ({cost_label}): {items}", self._account_id)
            else:
                msg = result.get("message", "")
                if "经验不足" in msg:
                    break
                warn("乐斗", "日常", f"宝箱开启失败: {msg}", self._account_id)
                break

            # Refresh status for next iteration
            status = await self._client.get_chest_status()
            if not status.get("success"):
                break
            data = status.get("data", {})
            next_cost = data.get("nextCost", 0) or 0

        if opened:
            log_action("乐斗", "日常", f"宝箱共 {opened} 次 (预算{max_cost}EXP)", self._account_id)
        return True
