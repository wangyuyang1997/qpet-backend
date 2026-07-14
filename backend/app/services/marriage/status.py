"""婚姻状态查询"""
from app.services.qpet_client import QPetClient


class MarriageStatus:
    """查询婚姻状态"""

    def __init__(self, client: QPetClient):
        self._client = client

    async def get(self) -> dict:
        """返回 {married, partner, partnerUserId, intimacy, todayGiftSent, todayBossDone}"""
        result = await self._client.get_marriage_status()
        if not result.get("success"):
            return {"married": False}
        return result.get("data", {})
