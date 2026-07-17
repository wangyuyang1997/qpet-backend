"""世界BOSS — 不需要帮派，先查status确认BOSS存活再打"""
import logging
from app.services.qpet_client import QPetClient
from app.core.logger import info, warn

logger = logging.getLogger(__name__)


class WorldBoss:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id

    async def run(self) -> bool:
        status = await self._client.api_call("GET", "/qpet/world-boss/status")
        if not status.get("success"):
            warn("乐斗", "世界BOSS", "获取世界BOSS状态API失败", self._account_id)
            return False

        data = status.get("data", {})
        if not data.get("alive", False):
            return False  # BOSS未复活，正常跳过

        prepare = await self._client.api_call("POST", "/qpet/world-boss/prepare")
        if not prepare.get("success"):
            warn("乐斗", "世界BOSS", "准备世界BOSS失败", self._account_id)
            return False

        battle_token = prepare.get("data", {}).get("battleToken", "")
        if not battle_token:
            warn("乐斗", "世界BOSS", "未获取到battleToken", self._account_id)
            return False

        settle = await self._client.api_call("POST", "/qpet/world-boss/settle", {"battleToken": battle_token, "atkWon": True})
        if settle.get("success"):
            info("乐斗", "世界BOSS", "世界BOSS完成", self._account_id)
            return True
        warn("乐斗", "世界BOSS", "世界BOSS结算失败", self._account_id)
        return False
