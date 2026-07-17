"""赛事报名 — 武林大会，对齐 game API /qpet/tournament/status"""
import logging
from app.services.qpet_client import QPetClient
from app.core.logger import info, warn

logger = logging.getLogger(__name__)


class Tournament:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id

    async def run(self, level: int = 0) -> dict:
        """返回 {registered: bool}"""
        results = {"registered": False}

        status = await self._client.get_tournament_status()
        if not status.get("success"):
            warn("乐斗", "赛事", "获取赛事状态API失败", self._account_id)
            return results

        data = status.get("data", {})
        reg_info = data.get("registrationInfo", {})

        # 已报名则跳过
        if reg_info.get("registered", False):
            return {"registered": True}

        result = await self._client.api_call("POST", "/qpet/tournament/register")
        results["registered"] = result.get("success", False)
        if results["registered"]:
            info("乐斗", "赛事", f"武林大会报名成功 (赛季{reg_info.get('seasonNumber','?')})", self._account_id)
        else:
            warn("乐斗", "赛事", f"武林大会报名失败: {result.get('message','无详情')}", self._account_id)

        return results
