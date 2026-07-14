"""赛事报名 — 武林大会+菜鸟大会"""
import logging
from app.services.qpet_client import QPetClient

logger = logging.getLogger(__name__)


class Tournament:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id

    async def run(self, level: int = 0) -> dict:
        """返回 {wulin: bool, loser: bool}"""
        results = {"wulin": False, "loser": False}

        status = await self._client.get_tournament_status()
        if not status.get("success"):
            return results

        data = status.get("data", {})

        if not data.get("wulinRegistered", False):
            result = await self._client.api_call("POST", "/qpet/tournament/register")
            results["wulin"] = result.get("success", False)
            if results["wulin"]:
                logger.info(f"[{self._account_id}] 武林大会报名成功")

        if level >= 100 and not data.get("loserRegistered", False):
            result = await self._client.api_call("POST", "/qpet/loser-tournament/register")
            results["loser"] = result.get("success", False)
            if results["loser"]:
                logger.info(f"[{self._account_id}] 菜鸟大会报名成功")

        return results
