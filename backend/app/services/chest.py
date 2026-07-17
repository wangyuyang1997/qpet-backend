"""宝箱自动化 — 典藏宝箱 + 展览厅宝箱"""
import logging
from app.services.qpet_client import QPetClient
from app.core.logger import action as log_action, warn

logger = logging.getLogger(__name__)


class Chest:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id

    async def run(self) -> dict:
        results = {}
        results["collection"] = await self._open_collection_chest()
        results["exhibition"] = await self._open_exhibition_chest()
        return results

    async def _open_collection_chest(self) -> bool:
        status = await self._client.get_chest_status()
        if not status.get("success"):
            warn("乐斗", "日常", "获取典藏宝箱状态API失败", self._account_id)
            return False
        data = status.get("data", {})
        if data.get("todayCount", 1) > 0 or not data.get("free", False):
            return False
        result = await self._client.open_chest()
        if result.get("success"):
            log_action("乐斗", "日常", "宝箱免费开启成功", self._account_id)
            return True
        warn("乐斗", "日常", "典藏宝箱开启失败", self._account_id)
        return False

    async def _open_exhibition_chest(self) -> bool:
        status = await self._client.get_exhibition_chest()
        if not status.get("success"):
            warn("乐斗", "日常", "获取展览厅宝箱状态API失败", self._account_id)
            return False
        data = status.get("data", {})
        if not data.get("canOpen", False):
            return False
        result = await self._client.open_exhibition_chest()
        if result.get("success"):
            log_action("乐斗", "日常", "展览厅宝箱已开", self._account_id)
            return True
        warn("乐斗", "日常", "展览厅宝箱开启失败", self._account_id)
        return False
