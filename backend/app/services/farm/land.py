"""农场统一土地养成 — 升级一次全农场所有土地统一升级"""
import logging
from sqlalchemy import select
from app.models.farm_land import FarmLand as FarmLandModel
from app.services.qpet_client import QPetClient

logger = logging.getLogger(__name__)


class FarmLand:

    def __init__(self, client: QPetClient, account_id: str, db_session_factory=None):
        self._client = client
        self._account_id = account_id
        self._sf = db_session_factory
        self.today_count = 0

    async def run(self, farm_data: dict) -> int:
        """统一土地升级。从 GET /farm 返回数据判断 canUpgrade，
        通过第一个地块的 upgrade-land 接口触发升级（升一级全农场生效）。
        返回 0 或 1。"""
        land = farm_data.get("land", {})
        if not land.get("canUpgrade", False):
            return 0

        # 新系统统一升级，用 slot 0 的接口触发
        prev_level = land.get("level", 1)
        next_name = land.get("next", {}).get("name", "?")

        ok = await self._client.farm_upgrade_land(0)
        if ok.get("success"):
            self.today_count += 1
            logger.info(
                f"[{self._account_id}] 统一土地升级: "
                f"Lv.{prev_level} -> {next_name} 升级成功"
            )
            return 1

        return 0
