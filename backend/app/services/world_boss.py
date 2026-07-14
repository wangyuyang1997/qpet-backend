"""世界BOSS — 不需要帮派，先查status确认BOSS存活再打"""
import logging
from app.services.qpet_client import QPetClient

logger = logging.getLogger(__name__)


class WorldBoss:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id

    async def run(self) -> bool:
        status = await self._client.api_call("GET", "/qpet/world-boss/status")
        if not status.get("success"):
            return False

        data = status.get("data", {})
        if not data.get("alive", False):
            return False

        prepare = await self._client.api_call("POST", "/qpet/world-boss/prepare")
        if not prepare.get("success"):
            return False

        battle_token = prepare.get("data", {}).get("battleToken", "")
        if not battle_token:
            return False

        settle = await self._client.api_call("POST", "/qpet/world-boss/settle", {"battleToken": battle_token, "atkWon": True})
        if settle.get("success"):
            logger.info(f"[{self._account_id}] 世界BOSS完成")
            return True
        return False
