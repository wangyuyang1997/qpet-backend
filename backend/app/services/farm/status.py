"""农场状态"""
import logging
from app.services.qpet_client import QPetClient

logger = logging.getLogger(__name__)


class FarmStatus:

    def __init__(self, client: QPetClient):
        self._client = client

    async def get(self) -> dict:
        result = await self._client.farm_get_status()
        if not result.get("success"):
            logger.warning("获取农场状态API失败")
            return {}
        return result.get("data", {})
