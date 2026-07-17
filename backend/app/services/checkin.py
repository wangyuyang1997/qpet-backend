"""每日签到 — 查状态，未签才 POST"""
import logging
from app.services.qpet_client import QPetClient
from app.core.logger import action as log_action, warn, info

logger = logging.getLogger(__name__)


class Checkin:
    """签到 service"""

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id

    async def run(self) -> bool:
        result = await self._client.get_checkin_info()
        if not result.get("success"):
            warn("乐斗", "日常", "获取签到状态API失败", self._account_id)
            return False

        data = result.get("data", {})
        if data.get("checkedIn", False):
            return True

        post = await self._client.checkin()
        if post.get("success"):
            log_action("乐斗", "日常", "签到成功", self._account_id)
            return True

        warn("乐斗", "日常", "签到POST失败", self._account_id)
        return False
