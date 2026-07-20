"""赛事报名 — 武林大会(/qpet/tournament) + 菜鸟大会(/qpet/loser-tournament)
Lv.100+ 报武林大会，<Lv.100 报菜鸟大会"""

import logging
from app.services.qpet_client import QPetClient
from app.core.logger import info, warn

logger = logging.getLogger(__name__)


class Tournament:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id

    async def run(self, level: int = 0) -> dict:
        """返回 {registered: bool, type: str}"""
        if level >= 100:
            return await self._register("tournament", "武林大会",
                                        self._client.get_tournament_status,
                                        "/qpet/tournament/register")
        else:
            return await self._register("loser", "菜鸟大会",
                                        self._client.get_loser_tournament_status,
                                        "/qpet/loser-tournament/register")

    async def _register(self, key: str, label: str, status_fn, register_path: str) -> dict:
        results: dict = {"registered": False}

        status = await status_fn()
        if not status.get("success"):
            warn("乐斗", "赛事", f"获取{label}状态API失败", self._account_id)
            return results

        data = status.get("data", {})
        reg_info = data.get("registrationInfo", {})

        if reg_info.get("registered", False):
            return {"registered": True, "type": label}

        result = await self._client.api_call("POST", register_path)
        results["registered"] = result.get("success", False)
        if results["registered"]:
            info("乐斗", "赛事", f"{label}报名成功 (赛季{reg_info.get('seasonNumber','?')})", self._account_id)
        else:
            warn("乐斗", "赛事", f"{label}报名失败: {result.get('message','无详情')}", self._account_id)

        return results
