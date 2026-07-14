"""宝箱自动化 — 典藏宝箱 + 展览厅宝箱"""
import logging
from app.services.qpet_client import QPetClient

logger = logging.getLogger(__name__)


class Chest:
    """宝箱 service"""

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id

    async def run(self) -> dict:
        results = {}
        results["collection"] = await self._open_collection_chest()
        results["exhibition"] = await self._open_exhibition_chest()
        return results

    async def _open_collection_chest(self) -> bool:
        """典藏宝箱：今日0次且免费才开"""
        status = await self._client.get_chest_status()
        if not status.get("success"):
            return False

        data = status.get("data", {})
        if data.get("todayCount", 1) > 0 or not data.get("free", False):
            return False

        result = await self._client.open_chest()
        if result.get("success"):
            logger.info(f"[{self._account_id}] 典藏宝箱已开")
            return True
        return False

    async def _open_exhibition_chest(self) -> bool:
        """展览厅宝箱"""
        status = await self._client.get_exhibition_chest()
        if not status.get("success"):
            return False

        data = status.get("data", {})
        if not data.get("canOpen", False):
            return False

        result = await self._client.open_exhibition_chest()
        if result.get("success"):
            logger.info(f"[{self._account_id}] 展览厅宝箱已开")
            return True
        return False
