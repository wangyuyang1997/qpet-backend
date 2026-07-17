"""每日签到 — 查状态，未签才 POST"""
import logging
from datetime import date
from app.services.qpet_client import QPetClient
from app.core.logger import action as log_action, warn, info

logger = logging.getLogger(__name__)


class Checkin:
    """签到 service"""

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id
        self._done_date: str = ""

    async def run(self) -> bool:
        today = date.today().isoformat()
        if self._done_date == today:
            return True

        result = await self._client.get_checkin_info()
        if not result.get("success"):
            return False

        data = result.get("data", {})
        if data.get("hasCheckedInToday") or data.get("checkedIn"):
            self._done_date = today
            return True

        post = await self._client.checkin()
        if post.get("success"):
            self._done_date = today
            log_action("乐斗", "日常", "签到成功", self._account_id)
            return True

        return False
