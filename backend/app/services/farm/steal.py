"""偷菜 — 生成mouseTrail，每周期2次"""
import asyncio
import json
import logging
from app.services.qpet_client import QPetClient

logger = logging.getLogger(__name__)


class FarmSteal:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id
        self.today_count = 0

    @staticmethod
    def _gen_mouse_trail(length: int = 12) -> list:
        import random
        return [{"x": random.randint(10, 290), "y": random.randint(10, 290), "t": i * 33} for i in range(length)]

    async def run(self, friend_id: str, max_count: int = 2) -> int:
        """偷好友菜，返回成功次数"""
        status = await self._client.farm_get_friend(friend_id)
        if not status.get("success"):
            logger.warning(f"[{self._account_id}] 偷菜: 获取好友农场失败 friend={friend_id} msg={status.get('message', '')}")
            return 0

        slots = status.get("data", {}).get("slots", [])
        ripe = [s for s in slots if s.get("canSteal") or s.get("state") in ("ripe", "mature", "ready")]
        if not ripe:
            logger.info(f"[{self._account_id}] 偷菜: 无可偷作物 friend={friend_id}")
        count = 0

        for slot in ripe[:max_count]:
            trail = self._gen_mouse_trail()
            ok = await self._client.farm_steal(friend_id, slot["slotIndex"], trail)
            if ok.get("success"):
                count += 1
                self.today_count += 1
            else:
                msg = ok.get("message", "")
                if any(kw in msg for kw in ("已偷过", "已偷完", "该作物已被偷完", "黑土地", "该地块没有作物", "仅成熟作物可偷取", "体力不足")):
                    logger.debug(f"[{self._account_id}] 偷菜跳过: {msg}")
                else:
                    logger.warning(f"[{self._account_id}] 偷菜失败: friend={friend_id} slot={slot['slotIndex']} msg={msg}")
            await asyncio.sleep(2.0)

        if count:
            from app.core.logger import action as log_action
            names = [s.get("cropName", f"地块{s['slotIndex']+1}") for s in ripe[:count]]
            log_action("农场", "偷菜", f"{friend_id}: {', '.join(names)} 完成: {count}次", self._account_id)
        return count
