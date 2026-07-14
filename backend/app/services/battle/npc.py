"""NPC 快速乐斗 — 每日10次"""
import logging
from app.services.qpet_client import QPetClient

logger = logging.getLogger(__name__)


class NpcBattle:
    """NPC 对战 service，每账号一个实例"""

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id

    async def fight_one(self) -> dict:
        """单次 NPC 战斗：prepare → settle"""
        result = await self._client.fight_npc()
        if not result.get("success"):
            msg = result.get("message", "")
            return {"ok": False, "reason": msg or "prepare失败"}

        data = result.get("data", {})
        battle_token = data.get("battleToken", "")
        if not battle_token:
            return {"ok": False, "reason": "无battleToken"}

        settle = await self._client.settle_battle(battle_token, True)
        if settle.get("success"):
            logger.debug(f"[{self._account_id}] NPC战斗胜利")
            return {"ok": True}

        return {"ok": False, "reason": settle.get("message", "settle失败")}
