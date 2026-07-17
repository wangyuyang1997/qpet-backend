"""NPC 快速乐斗 — 每日10次"""
import logging
from app.services.qpet_client import QPetClient
from app.core.logger import action, warn

logger = logging.getLogger(__name__)


class NpcBattle:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id
        self.today_count = 0
        self.today_exp = 0

    async def fight_one(self) -> dict:
        result = await self._client.fight_npc()
        if not result.get("success"):
            msg = result.get("message", "")
            if "体力" in msg or "stamina" in msg:
                return {"ok": False, "reason": msg, "no_stamina": True}
            warn("乐斗", "NPC乐斗", f"NPC准备失败: {msg}", self._account_id)
            return {"ok": False, "reason": msg or "prepare失败"}

        data = result.get("data", {}) or {}
        battle_token = data.get("battleToken", "")
        if not battle_token:
            warn("乐斗", "NPC乐斗", "缺少battleToken", self._account_id)
            return {"ok": False, "reason": "无battleToken"}

        settle = await self._client.settle_battle(battle_token, True)
        if settle.get("success"):
            self.today_count += 1
            sd = settle.get("data", {}) or {}
            exp = sd.get("exp", 0) or sd.get("expGained", 0) or 0
            self.today_exp += exp
            action("乐斗", "NPC乐斗", f"{'胜' if exp > 0 else '败'} +{exp}EXP", self._account_id)
            return {"ok": True}

        warn("乐斗", "NPC乐斗", f"NPC结算失败: {settle.get('message', '')}", self._account_id)
        return {"ok": False, "reason": settle.get("message", "settle失败")}
