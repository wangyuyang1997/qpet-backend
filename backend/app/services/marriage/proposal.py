"""求婚/接受求婚 — 亲密度≥100触发"""
import logging
from app.services.qpet_client import QPetClient

logger = logging.getLogger(__name__)


class MarriageProposal:
    """求婚流程"""

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id

    async def run(self, status: dict) -> bool:
        """检测pending请求→接受，否则主动求婚"""
        if status.get("married"):
            return False

        data = status.get("data", status)
        pending = data.get("pendingProposal", False) or data.get("hasPendingRequest", False)

        if pending:
            result = await self._client.respond_marriage(True)
            if result.get("success"):
                logger.info(f"[{self._account_id}] 已接受求婚")
                return True
            return False

        intimacy = data.get("intimacy", 0)
        if intimacy >= 100:
            result = await self._client.propose_marriage()
            if result.get("success"):
                logger.info(f"[{self._account_id}] 已发起求婚")
                return True

        return False
