"""宝箱自动化 — 展览厅宝箱，对齐旧引擎 autoChest()"""
import logging
from datetime import date
from app.services.qpet_client import QPetClient
from app.core.logger import action as log_action, warn

logger = logging.getLogger(__name__)


class Chest:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id
        self._done_date: str = ""

    async def run(self) -> bool:
        today = date.today().isoformat()
        if self._done_date == today:
            return True

        status = await self._client.get_chest_status()
        if not status.get("success"):
            warn("乐斗", "日常", "获取宝箱状态失败", self._account_id)
            return False
        data = status.get("data", {})
        # 对齐旧引擎: nextCost>0 且 todayCount>0 表示今日已开过
        if (data.get("nextCost", 0) or 0) > 0 and (data.get("todayCount", 0) or 0) > 0:
            self._done_date = today
            return True

        result = await self._client.open_chest()
        if result.get("success"):
            log_action("乐斗", "日常", "宝箱免费开启成功", self._account_id)
            self._done_date = today
            return True

        msg = result.get("message", "")
        if "经验不足" in msg:
            return False  # 经验不够，不记日志
        warn("乐斗", "日常", f"宝箱开启失败: {msg}", self._account_id)
        return False
