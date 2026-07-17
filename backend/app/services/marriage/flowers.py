"""好友送花 — 未婚专用，POST friend/flower，亲密度≥100触发求婚"""
import logging
from app.services.qpet_client import QPetClient
from app.services.item_supply import ItemSupply
from app.core.logger import info, warn

logger = logging.getLogger(__name__)


class MarriageFlowers:
    """好友送花，每天10次，亲密度≥100停止"""

    def __init__(self, client: QPetClient, supply: ItemSupply, account_id: str):
        self._client = client
        self._supply = supply
        self._account_id = account_id

    async def run(self, marriage_partner_id: str | None, intimacy: int, today_sent: int = 0) -> dict:
        """返回 {sent, intimacy}，供 engine 判断是否触发求婚"""
        if not marriage_partner_id:
            return {"sent": 0, "intimacy": intimacy}

        if intimacy >= 100:
            return {"sent": 0, "intimacy": intimacy}

        max_sends = 10
        count = 0

        while today_sent + count < max_sends and intimacy < 100:
            result = await self._client.send_friend_flower(marriage_partner_id)
            if not result.get("success"):
                await self._supply.ensure("flowers", 0)
                result = await self._client.send_friend_flower(marriage_partner_id)
                if not result.get("success"):
                    warn("乐斗", "婚姻", "好友送花失败(已补花重试)", self._account_id)
                    break

            count += 1
            intimacy += 10  # 估算

        if count:
            info("乐斗", "婚姻", f"好友送花 {count}次", self._account_id)

        return {"sent": count, "intimacy": intimacy}
