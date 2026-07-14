"""农场状态"""
from app.services.qpet_client import QPetClient


class FarmStatus:

    def __init__(self, client: QPetClient):
        self._client = client

    async def get(self) -> dict:
        result = await self._client.farm_get_status()
        if not result.get("success"):
            return {}
        return result.get("data", {})
