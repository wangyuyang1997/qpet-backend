"""夫妻BOSS — 每日1次"""
import logging
from app.services.qpet_client import QPetClient

logger = logging.getLogger(__name__)


class MarriageBoss:
    """夫妻BOSS战斗"""

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id

    async def run(self, status: dict) -> bool:
        if not status.get("married"):
            return False
        if status.get("todayBossDone", False):
            return False

        result = await self._client.prepare_marriage_boss()
        if not result.get("success"):
            return False

        battle_token = result.get("data", {}).get("battleToken", "")
        if not battle_token:
            return False

        settle = await self._client.settle_marriage_boss(battle_token, True)
        if settle.get("success"):
            logger.info(f"[{self._account_id}] 夫妻BOSS完成")
            return True

        return False
