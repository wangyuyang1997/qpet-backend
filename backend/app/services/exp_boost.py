"""经验药水 BUFF — 检查角色经验加成，不足时从背包补充"""
import logging
from app.services.qpet_client import QPetClient
from app.services.inventory import Inventory
from app.services.config_service import ConfigService
from app.core.logger import info, warn

logger = logging.getLogger(__name__)


class ExpBoost:
    """每账号一个实例，engine 战斗前统一调用"""

    def __init__(self, client: QPetClient, inventory: Inventory, config_svc: ConfigService, account_id: str):
        self._client = client
        self._inventory = inventory
        self._config = config_svc
        self._account_id = account_id

    async def ensure(self, threshold: int = 5) -> bool:
        """经验 BUFF 次数 ≤ threshold 时从背包补充"""
        char = await self._client.get_character()
        if not char.get("success"):
            warn("乐斗", "补给", "获取角色信息失败(经验药水检查)", self._account_id)
            return False

        data = char.get("data", {})
        charges = data.get("exp_boost_charges", 0)
        if charges > threshold:
            return False

        enabled = await self._config.get_bool(self._account_id, "exp_boost_enabled")
        if not enabled:
            return False

        result = await self._inventory.use_by_name("经验")
        if result and result.get("success"):
            info("乐斗", "补给", f"经验药水补充成功 (剩余{charges}次)", self._account_id)
            return True

        warn("乐斗", "补给", "经验药水补充失败 (背包无药水或API失败)", self._account_id)
        return False
