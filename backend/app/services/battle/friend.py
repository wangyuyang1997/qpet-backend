"""好友对战 — Lv40+过滤 → 等级接近前8 → 战力最接近的1人"""
import logging
from app.services.qpet_client import QPetClient

logger = logging.getLogger(__name__)


class FriendBattle:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id

    async def pick_target(self, self_level: int = 0) -> dict | None:
        """选择最匹配的对手"""
        result = await self._client.get_fightable_friends()
        if not result.get("success"):
            return None

        friends = result.get("data", {}).get("friends", [])
        candidates = [f for f in friends if f.get("level", 0) >= 40 and f.get("level", 0) != self_level]
        if not candidates:
            return None

        candidates.sort(key=lambda f: abs(f.get("level", 0) - self_level))
        best = candidates[:8]
        best.sort(key=lambda f: abs(f.get("combatPower", 0) - self_level))
        return best[0] if best else None

    async def fight_one(self, target: dict) -> dict:
        """单次好友对战"""
        target_id = target.get("userId") or target.get("id")
        result = await self._client.fight_player(target_id)
        if not result.get("success"):
            return {"ok": False, "reason": result.get("message", "prepare失败")}

        battle_token = result.get("data", {}).get("battleToken", "")
        if not battle_token:
            return {"ok": False, "reason": "无battleToken"}

        settle = await self._client.settle_battle(battle_token, True)
        if settle.get("success"):
            logger.info(f"[{self._account_id}] 好友对战胜利 vs {target.get('nickname', target_id)}")
            return {"ok": True}

        return {"ok": False, "reason": settle.get("message", "settle失败")}
