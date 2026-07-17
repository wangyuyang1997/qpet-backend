"""宝箱自动化 — 典藏宝箱 + 展览厅宝箱"""
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

    async def run(self) -> dict:
        today = date.today().isoformat()
        if self._done_date == today:
            return {"collection": True, "exhibition": True}

        results = {}
        results["collection"] = await self._open_collection_chest()
        results["exhibition"] = await self._open_exhibition_chest()

        if results["collection"] and results["exhibition"]:
            self._done_date = today
        return results

    async def _open_collection_chest(self) -> bool:
        status = await self._client.get_chest_status()
        if not status.get("success"):
            return False
        data = status.get("data", {})
        if data.get("todayCount", 1) > 0 or not data.get("free", False):
            return True  # 今天已经开过或无免费次数，视为完成
        result = await self._client.open_chest()
        if result.get("success"):
            log_action("乐斗", "日常", "宝箱免费开启成功", self._account_id)
            return True
        return False

    async def _open_exhibition_chest(self) -> bool:
        status = await self._client.get_exhibition_chest()
        if not status.get("success"):
            return False
        data = status.get("data", {})
        if not data.get("canOpen", False):
            return True  # 今日已开过，视为完成
        result = await self._client.open_exhibition_chest()
        if result.get("success"):
            log_action("乐斗", "日常", "展览厅宝箱已开", self._account_id)
            return True
        return False
