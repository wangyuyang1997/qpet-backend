"""赛事报名 — 武林大会(/qpet/tournament) + 菜鸟大会(/qpet/loser-tournament)
两者都需 Lv.100，满级角色两个都报"""

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
        if level < 100:
            return {"registered": False}

        results = {"registered": False}

        # 武林大会
        r = await self._register("武林大会",
                                 self._client.get_tournament_status,
                                 "/qpet/tournament/register")
        if r:
            results["registered"] = True

        # 菜鸟大会(败者组)
        r = await self._register("菜鸟大会",
                                 self._client.get_loser_tournament_status,
                                 "/qpet/loser-tournament/register")
        if r:
            results["registered"] = True

        return results

    async def _register(self, label: str, status_fn, register_path: str) -> bool:

        status = await status_fn()
        if not status.get("success"):
            warn("乐斗", "赛事", f"获取{label}状态API失败", self._account_id)
            return False

        data = status.get("data", {})
        reg_info = data.get("registrationInfo", {})

        if reg_info.get("registered", False):
            return True  # 已报名，不算失败

        result = await self._client.api_call("POST", register_path)
        if result.get("success"):
            info("乐斗", "赛事", f"{label}报名成功 (赛季{reg_info.get('seasonNumber','?')})", self._account_id)
            return True
        else:
            warn("乐斗", "赛事", f"{label}报名失败: {result.get('message','无详情')}", self._account_id)
            return False
