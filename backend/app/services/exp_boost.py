"""经验药水 BUFF — 检查角色经验加成，不足时从背包补充"""
import logging
from datetime import date
from app.services.qpet_client import QPetClient
from app.services.inventory import Inventory
from app.services.config_service import ConfigService
from app.core.logger import info

logger = logging.getLogger(__name__)


class ExpBoost:
    """每账号一个实例，engine 战斗前统一调用"""

    def __init__(self, client: QPetClient, inventory: Inventory, config_svc: ConfigService, account_id: str):
        self._client = client
        self._inventory = inventory
        self._config = config_svc
        self._account_id = account_id
        self._failed_date: str = ""

    async def ensure(self) -> bool:
        """经验 BUFF 次数用完时从背包补充，优先中瓶再小瓶"""
        today = date.today().isoformat()
        if self._failed_date == today:
            return False

        char = await self._client.get_character()
        if not char.get("success"):
            return False

        data = char.get("data", {})
        if data.get("level", 0) >= 100:
            return False  # 满级不需要经验
        charges = data.get("exp_boost_charges", 0)
        if charges > 0:
            return False  # 上一瓶还没用完

        enabled = await self._config.get_bool(self._account_id, "exp_boost_enabled")
        if not enabled:
            return False

        # 优先中瓶，再小瓶
        result = await self._inventory.use_by_name("中瓶经验") or await self._inventory.use_by_name("小瓶经验")
        if result and result.get("success"):
            info("乐斗", "补给", "经验药水补充成功", self._account_id)
            return True

        self._failed_date = today
        return False
